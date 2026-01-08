# EMA20 Experiments Archive
# Combined on 2026-01-08


# ========== FROM: test_ema20_2sd_daily_exit.py ==========

#!/usr/bin/env python3
"""
EMA 20 / 2.0SD Strategy - Daily Entry/Exit Version
Uses weekly data for signal detection, daily data for exact entry/exit
Combined results for Large + Mid baskets
"""

import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Configuration
MA_TYPE = "EMA"
MA_PERIOD = 20
BB_SD = 2.0
SL_PCT = 0.20  # 20% stop loss
TRANSACTION_COST = 0.0037  # 0.37% total

CACHE_DIR = Path("data/cache/dhan/daily")

# Baskets
LARGE_BASKET = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "BHARTIARTL", "INFY", "SBIN",
    "ITC", "HINDUNILVR", "LT", "BAJFINANCE", "HCLTECH", "MARUTI", "SUNPHARMA",
    "ADANIENT", "KOTAKBANK", "AXISBANK", "ONGC", "TITAN", "NTPC", "ADANIPORTS",
    "ULTRACEMCO", "ASIANPAINT", "COALINDIA", "BAJAJFINSV", "TATAMOTORS",
    "POWERGRID", "NESTLEIND", "M&M", "JSWSTEEL", "TATASTEEL", "WIPRO",
    "HDFCLIFE", "TECHM", "GRASIM", "DRREDDY", "BRITANNIA", "HINDALCO",
    "BAJAJ-AUTO", "INDUSINDBK", "CIPLA", "SBILIFE", "DIVISLAB", "EICHERMOT",
    "BPCL", "TATACONSUM", "APOLLOHOSP", "HEROMOTOCO", "SHRIRAMFIN", "VEDL",
    "ZOMATO", "ADANIGREEN", "DABUR", "INDIGO", "GODREJCP", "SIEMENS",
    "TRENT", "DLF", "BEL", "BANKBARODA", "IOC", "PNB", "HAVELLS", "ABB",
    "JIOFIN", "AMBUJACEM", "GAIL", "PIDILITIND", "CHOLAFIN", "CANBK",
    "TATAPOWER", "PFC", "RECLTD", "HAL", "MANKIND", "TORNTPHARM", "VBL",
    "UNIONBANK", "ATGL", "ICICIPRULI", "ZYDUSLIFE", "INDIANB", "LODHA",
    "POLYCAB", "NHPC", "IRFC", "JSWENERGY", "NAUKRI", "COLPAL", "CGPOWER",
    "BOSCHLTD", "PERSISTENT", "INDUSTOWER", "ICICIGI", "JINDALSTEL", "SRF",
    "IOB", "IDBI", "MAXHEALTH", "HDFCAMC", "MOTHERSON", "INDHOTEL", "TMPV"
]

MID_BASKET = [
    "ADANIPOWER", "MCDOWELL-N", "IRCTC", "PIIND", "NMDC", "PAGEIND", "ACC",
    "MUTHOOTFIN", "CONCOR", "AUROPHARMA", "CUMMINSIND", "LICHSGFIN",
    "OBEROIRLTY", "TIINDIA", "FEDERALBNK", "HINDPETRO", "LUPIN", "PETRONET",
    "BALKRISIND", "GODREJPROP", "LTIM", "ASTRAL", "SOLARINDS", "GMRAIRPORT",
    "COFORGE", "BHARATFORG", "TATACOMM", "DELHIVERY", "BHEL", "PRESTIGE",
    "VOLTAS", "APLAPOLLO", "MARICO", "SUPREMEIND", "MPHASIS", "BIOCON",
    "SAIL", "ALKEM", "SYNGENE", "IDFCFIRSTB", "LALPATHLAB", "ABCAPITAL",
    "TVSMOTOR", "IDEA", "UBL", "MRF", "BANDHANBNK", "LTTS", "KPITTECH",
    "SONACOMS", "AUBANK", "AJANTPHARM", "PATANJALI", "ESCORTS", "LAURUSLABS",
    "APOLLOTYRE", "NATIONALUM", "PEL", "UPL", "OFSS", "MFSL", "CROMPTON",
    "JKCEMENT", "ASHOKLEY", "L&TFH", "FORTIS", "YESBANK", "COROMANDEL",
    "HONAUT", "SUNTV", "DEEPAKNTR", "TATAELXSI", "IGL", "KANSAINER",
    "CENTRALBK", "NIACL", "SCHAEFFLER", "PHOENIXLTD", "GICRE", "LINDEINDIA",
    "NAM-INDIA", "KEI", "THERMAX", "KALYANKJIL", "ABFRL", "M&MFIN",
    "CRISIL", "BANKINDIA", "RAMCOCEM", "ZEEL", "EXIDEIND", "BSE",
    "SUNDARMFIN", "CLEAN", "SUZLON", "OIL", "TATATECH", "JSWINFRA", "LLOYDSME",
    "FACT", "POONAWALLA", "RADICO", "MOTILALOFS", "HINDCOPPER", "MAHABANK",
    "KAJARIACER", "GLAXO", "METROBRAND", "RELAXO", "SJVN", "IRB", "MRPL",
    "STARHEALTH", "DMART", "BERGEPAINT", "RAYMOND", "BATAINDIA", "POLICYBZR",
    "RBLBANK", "PNBHOUSING", "NLCINDIA", "KAYNES", "ITI", "NATCOPHARM",
    "CUB", "RVNL", "GUJGASLTD", "MSUMI", "AIAENG", "JSL", "HFCL", "NBCC",
    "HUDCO", "CARBORUNIV", "JBCHEPHARM", "BLUEDART", "PGHH", "ZFCVINDIA",
    "IREDA", "INOXWIND", "CDSL", "CREDITACC", "COCHINSHIP", "CESC", "ENDURANCE",
    "CYIENT", "FIVESTAR", "FSL", "TIMKEN", "IDFC", "SKFINDIA", "GODREJIND",
    "OLECTRA", "KPRMILL", "3MINDIA", "SHYAMMETL", "EIDPARRY", "GSFC", "GRINDWELL",
    "GNFC", "EMAMILTD", "GLENMARK", "GRAPHITE", "ZENSARTECH", "LUXIND",
    "BRIGADE", "CHOLAHLDNG", "HAPPSTMNDS", "APTUS", "SUVENPHAR", "360ONE",
    "BDL", "ATUL", "JYOTHYLAB", "SUMICHEM", "NUVAMA", "SOBHA", "LXCHEM",
    "TRITURBINE", "HEXT", "ACE", "FINCABLES", "BLUESTARCO", "MGL", "INDIAMART",
    "RHIM", "ELGIEQUIP", "RATNAMANI", "VTL", "CHALET", "REDINGTON", "IEX",
    "APARINDS", "GESHIP", "NEULANDLAB", "TRIVENI", "FINPIPE", "WELSPUNLIV",
    "KRBL", "NYKAA", "KIMS", "ANURAS", "BALAMINES", "AFFLE", "ABSLAMC",
    "ASAHIINDIA", "JUBLPHARMA", "SCHNEIDER", "POWERMECH", "CCL", "DATAPATTNS",
    "MANAPPURAM", "PGHL", "AWL", "BIRLACORPN", "VGUARD", "GPIL", "AMBER",
    "SWANENERGY"
]


def load_daily_data(symbol: str) -> pd.DataFrame:
    """Load daily OHLC data for a symbol"""
    # Files are named: dhan_{id}_{SYMBOL}_1d.csv
    pattern = f"dhan_*_{symbol}_1d.csv"
    matches = list(CACHE_DIR.glob(pattern))
    
    if not matches:
        return pd.DataFrame()
    
    file_path = matches[0]
    df = pd.read_csv(file_path)
    if 'time' in df.columns:
        df = df.rename(columns={'time': 'date'})
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    return df


def resample_to_weekly(daily_df: pd.DataFrame) -> pd.DataFrame:
    """Resample daily data to weekly OHLC"""
    df = daily_df.copy()
    df = df.set_index('date')
    
    weekly = df.resample('W-FRI').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    
    weekly = weekly.reset_index()
    return weekly


def calculate_indicators(weekly_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate BB and EMA on weekly data"""
    df = weekly_df.copy()
    
    # BB on close
    df['sma20'] = df['close'].rolling(20).mean()
    df['std20'] = df['close'].rolling(20).std()
    df['bb_lower'] = df['sma20'] - BB_SD * df['std20']
    
    # EMA for TP target
    df['ema20'] = df['close'].ewm(span=MA_PERIOD, adjust=False).mean()
    
    return df


def find_entry_day(daily_df: pd.DataFrame, signal_week_end: pd.Timestamp) -> tuple:
    """Find the first trading day after signal week end (Monday open)"""
    # Look for first trading day after the signal week
    next_days = daily_df[daily_df['date'] > signal_week_end].head(5)
    
    if len(next_days) == 0:
        return None, None
    
    entry_row = next_days.iloc[0]
    return entry_row['date'], entry_row['open']


def find_exit_day_daily(daily_df: pd.DataFrame, weekly_df: pd.DataFrame,
                        entry_date: pd.Timestamp, entry_price: float, 
                        sl_price: float, entry_week_idx: int) -> tuple:
    """
    Find exact exit day using daily data.
    TP: first day where high >= Weekly EMA 20 (recalculated each week)
    SL: first day where low <= sl_price
    Returns: (exit_date, exit_price, exit_reason)
    """
    # Get data from entry onwards
    df = daily_df[daily_df['date'] >= entry_date].copy()
    
    if len(df) < 2:
        return None, None, "DATA_END"
    
    # Skip entry day, start checking from day after entry
    df = df.iloc[1:]
    
    for _, row in df.iterrows():
        # Find which week this day belongs to
        day_date = row['date']
        
        # Find the weekly EMA value for this week
        # The weekly bar that this day falls into
        week_mask = weekly_df['date'] >= day_date
        if not week_mask.any():
            # Use last available weekly EMA
            weekly_ema = weekly_df['ema20'].iloc[-1]
        else:
            # Find the week end date >= day_date, then get that week's EMA
            week_idx = weekly_df[week_mask].index[0]
            # Use the EMA from the START of this week (previous week's close EMA)
            # to avoid look-ahead bias
            if week_idx > 0:
                weekly_ema = weekly_df.iloc[week_idx - 1]['ema20']
            else:
                weekly_ema = weekly_df.iloc[0]['ema20']
        
        if pd.isna(weekly_ema):
            continue
        
        # Check SL first (more conservative)
        if row['low'] <= sl_price:
            return row['date'], sl_price, "SL_HIT"
        
        # Check TP - high touches weekly EMA 20
        if row['high'] >= weekly_ema:
            # Exit at weekly EMA level
            exit_price = weekly_ema
            return row['date'], exit_price, "TP_HIT"
    
    # Data ended without exit
    last_row = df.iloc[-1] if len(df) > 0 else daily_df.iloc[-1]
    return last_row['date'], last_row['close'], "DATA_END"


def analyze_symbol(symbol: str) -> list:
    """Analyze a single symbol and return all trades"""
    trades = []
    
    # Load daily data
    daily_df = load_daily_data(symbol)
    if len(daily_df) < 100:
        return trades
    
    # Resample to weekly
    weekly_df = resample_to_weekly(daily_df)
    if len(weekly_df) < 25:
        return trades
    
    # Calculate weekly indicators
    weekly_df = calculate_indicators(weekly_df)
    
    last_exit_date = None
    
    for i in range(2, len(weekly_df) - 1):
        row = weekly_df.iloc[i]
        prev_row = weekly_df.iloc[i - 1]
        
        # Skip if in a trade (overlap protection)
        if last_exit_date and row['date'] <= last_exit_date:
            continue
        
        # Skip if missing data
        if pd.isna(row['bb_lower']) or pd.isna(row['ema20']):
            continue
        
        # Entry conditions on weekly bar
        is_green = row['close'] > row['open']
        opens_below_bb = row['open'] < row['bb_lower']
        body = abs(row['close'] - row['open'])
        prev_body = abs(prev_row['close'] - prev_row['open'])
        bigger_body = body > prev_body
        
        if is_green and opens_below_bb and bigger_body:
            # Signal detected - find entry on daily data
            signal_week_end = row['date']
            
            entry_date, entry_price = find_entry_day(daily_df, signal_week_end)
            
            if entry_date is None or entry_price is None or entry_price <= 0:
                continue
            
            # Calculate SL
            sl_price = entry_price * (1 - SL_PCT)
            
            # Find exit using daily data with weekly EMA target
            exit_date, exit_price, exit_reason = find_exit_day_daily(
                daily_df, weekly_df, entry_date, entry_price, sl_price, i
            )
            
            if exit_date is None or exit_price is None:
                continue
            
            # Calculate return
            gross_return = (exit_price - entry_price) / entry_price
            net_return = gross_return - TRANSACTION_COST
            
            days_held = (exit_date - entry_date).days
            
            trades.append({
                'symbol': symbol,
                'signal_date': signal_week_end,
                'entry_date': entry_date,
                'entry_price': entry_price,
                'exit_date': exit_date,
                'exit_price': exit_price,
                'exit_reason': exit_reason,
                'sl_price': sl_price,
                'gross_return': gross_return,
                'net_return': net_return,
                'days_held': days_held,
                'year': entry_date.year
            })
            
            last_exit_date = exit_date
    
    return trades


def main():
    print("=" * 70)
    print("🔬 EMA 20 / 2.0SD STRATEGY - DAILY ENTRY/EXIT")
    print("=" * 70)
    print(f"\nStrategy Parameters:")
    print(f"   • Signal: Weekly green candle + Opens below BB {BB_SD} SD + Bigger body")
    print(f"   • Entry: First trading day after signal week at OPEN")
    print(f"   • Exit TP: Daily HIGH >= Weekly EMA {MA_PERIOD} (prev week)")
    print(f"   • Exit SL: Daily LOW <= Entry × {1 - SL_PCT:.0%}")
    print(f"   • Transaction Cost: {TRANSACTION_COST:.2%}")
    print()
    
    # Combine baskets
    all_symbols = list(set(LARGE_BASKET + MID_BASKET))
    print(f"📊 Analyzing {len(all_symbols)} unique symbols (Large + Mid combined)...")
    print()
    
    all_trades = []
    symbols_with_trades = 0
    
    for symbol in all_symbols:
        trades = analyze_symbol(symbol)
        if trades:
            all_trades.extend(trades)
            symbols_with_trades += 1
    
    if not all_trades:
        print("No trades found!")
        return
    
    trades_df = pd.DataFrame(all_trades)
    
    # Calculate statistics
    total_trades = len(trades_df)
    winners = trades_df[trades_df['net_return'] > 0]
    losers = trades_df[trades_df['net_return'] <= 0]
    
    win_rate = len(winners) / total_trades * 100
    avg_return = trades_df['net_return'].mean() * 100
    median_return = trades_df['net_return'].median() * 100
    std_return = trades_df['net_return'].std() * 100
    total_return = trades_df['net_return'].sum() * 100
    
    gross_profit = winners['net_return'].sum() if len(winners) > 0 else 0
    gross_loss = abs(losers['net_return'].sum()) if len(losers) > 0 else 0.0001
    profit_factor = gross_profit / gross_loss
    
    avg_winner = winners['net_return'].mean() * 100 if len(winners) > 0 else 0
    avg_loser = losers['net_return'].mean() * 100 if len(losers) > 0 else 0
    avg_days = trades_df['days_held'].mean()
    
    # Print summary
    print("=" * 70)
    print("COMBINED RESULTS (LARGE + MID)")
    print("=" * 70)
    print()
    print(f"📊 Summary Statistics:")
    print(f"   Symbols Traded:  {symbols_with_trades}")
    print(f"   Total Trades:    {total_trades}")
    print(f"   Win Rate:        {win_rate:.1f}%")
    print(f"   Profit Factor:   {profit_factor:.2f}")
    print()
    print(f"   Avg Return:      {avg_return:+.2f}%")
    print(f"   Median Return:   {median_return:+.2f}%")
    print(f"   Std Dev:         {std_return:.2f}%")
    print(f"   Total Return:    {total_return:+.1f}%")
    print()
    print(f"   Avg Winner:      {avg_winner:+.2f}%")
    print(f"   Avg Loser:       {avg_loser:+.2f}%")
    print(f"   Best Trade:      {trades_df['net_return'].max() * 100:+.2f}%")
    print(f"   Worst Trade:     {trades_df['net_return'].min() * 100:+.2f}%")
    print(f"   Avg Days Held:   {avg_days:.1f}")
    print()
    
    # Percentiles
    print("📈 Percentiles:")
    for p in [5, 10, 25, 50, 75, 90, 95]:
        val = trades_df['net_return'].quantile(p / 100) * 100
        print(f"   P{p:2d}:  {val:+.2f}%")
    print()
    
    # Return buckets
    print("📦 Return Distribution:")
    buckets = [
        ("Heavy Loss (< -15%)", -100, -15),
        ("Moderate Loss (-15/-10)", -15, -10),
        ("Small Loss (-10/-5)", -10, -5),
        ("Minor Loss (-5/0)", -5, 0),
        ("Minor Gain (0/5)", 0, 5),
        ("Small Gain (5/10)", 5, 10),
        ("Moderate Gain (10/20)", 10, 20),
        ("Good Gain (20/50)", 20, 50),
        ("Excellent (50%+)", 50, 200),
    ]
    
    for label, low, high in buckets:
        count = len(trades_df[(trades_df['net_return'] * 100 >= low) & 
                              (trades_df['net_return'] * 100 < high)])
        pct = count / total_trades * 100
        bar = "█" * int(pct / 2)
        if count > 0:
            print(f"   {label:<25} | {count:4d} ({pct:5.1f}%) {bar}")
    print()
    
    # Exit reasons
    print("🚪 Exit Reasons:")
    for reason in trades_df['exit_reason'].unique():
        subset = trades_df[trades_df['exit_reason'] == reason]
        count = len(subset)
        pct = count / total_trades * 100
        avg_ret = subset['net_return'].mean() * 100
        print(f"   {reason:<10}: {count:4d} ({pct:5.1f}%) | Avg Return: {avg_ret:+.2f}%")
    print()
    
    # Year-wise performance
    print("📅 Year-wise Performance:")
    yearly = trades_df.groupby('year').agg({
        'net_return': ['count', 'mean', 'median', 'sum'],
        'exit_reason': lambda x: (x == 'SL_HIT').sum()
    }).round(2)
    yearly.columns = ['Trades', 'Avg%', 'Med%', 'Total%', 'SL_Hits']
    yearly['Avg%'] = (yearly['Avg%'] * 100).round(2)
    yearly['Med%'] = (yearly['Med%'] * 100).round(2)
    yearly['Total%'] = (yearly['Total%'] * 100).round(2)
    yearly['Win%'] = ((yearly['Trades'] - yearly['SL_Hits']) / yearly['Trades'] * 100).round(1)
    print(yearly.to_string())
    print()
    
    # Top/Bottom symbols
    symbol_perf = trades_df.groupby('symbol').agg({
        'net_return': ['count', 'mean', 'sum']
    }).round(4)
    symbol_perf.columns = ['Trades', 'Avg%', 'Total%']
    symbol_perf['Avg%'] = (symbol_perf['Avg%'] * 100).round(2)
    symbol_perf['Total%'] = (symbol_perf['Total%'] * 100).round(2)
    
    print("🏆 Top 15 Symbols:")
    top = symbol_perf.nlargest(15, 'Total%')
    print(top.to_string())
    print()
    
    print("📉 Bottom 15 Symbols:")
    bottom = symbol_perf.nsmallest(15, 'Total%')
    print(bottom.to_string())
    print()
    
    # Save trades
    output_path = Path("reports/ema20_2sd_daily_combined_trades.csv")
    trades_df.to_csv(output_path, index=False)
    print(f"💾 Saved: {output_path}")
    
    # Print comparison with weekly version
    print()
    print("=" * 70)
    print("KEY INSIGHTS")
    print("=" * 70)
    print("""
1. DAILY EXIT PRECISION:
   - Exits now happen on the exact day when TP/SL is triggered
   - TP = Daily HIGH touches Daily EMA 20
   - SL = Daily LOW touches entry × 80%

2. ENTRY PRECISION:
   - Entry at OPEN of first trading day after signal week
   - No Friday close assumption

3. REMAINING LIMITATIONS:
   - Survivorship bias (ignored per request)
   - Intraday ambiguity when both SL and TP could hit same day
     (we check SL first as conservative approach)

4. TP TARGET CLARIFICATION:
   - TP uses WEEKLY EMA 20 (previous week's value to avoid look-ahead)
   - Daily HIGH is checked against this weekly target
   - This matches the original weekly strategy intent
""")


if __name__ == "__main__":
    main()


# ========== FROM: test_ema20_2sd_detailed.py ==========

#!/usr/bin/env python3
"""
EMA 20 / 2.0SD Strategy - Detailed Analysis & Critique
=======================================================
Focus on LARGE and MID baskets
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import timedelta
import glob
from typing import Dict, List, Tuple, Optional

CACHE_DIR = Path("data/cache/dhan/daily")
TRANSACTION_COST_PCT = 0.37
FIXED_SL_PCT = 20.0
MA_TYPE = "EMA"
MA_PERIOD = 20
SD_LEVEL = 2.0


def load_basket(path: str) -> List[str]:
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def load_ohlc_data(symbol: str) -> Optional[pd.DataFrame]:
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
    if len(df) < 10:
        return pd.DataFrame()
    
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["year_week"] = df["date"].dt.strftime("%Y-%W")
    
    weekly = df.groupby("year_week", sort=False).agg({
        "date": ["first", "last"],
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    })
    
    weekly.columns = ["week_start", "week_end", "open", "high", "low", "close", "volume"]
    weekly = weekly.reset_index()
    weekly = weekly.sort_values("week_start").reset_index(drop=True)
    weekly["body"] = abs(weekly["close"] - weekly["open"])
    
    # Add indicators
    weekly["ema20"] = weekly["close"].ewm(span=MA_PERIOD, adjust=False).mean()
    sma = weekly["close"].rolling(window=MA_PERIOD).mean()
    std = weekly["close"].rolling(window=MA_PERIOD).std()
    weekly["bb_lower"] = sma - (std * SD_LEVEL)
    
    return weekly


def identify_signals(weekly_df: pd.DataFrame) -> pd.DataFrame:
    if len(weekly_df) < MA_PERIOD + 5:
        return pd.DataFrame()
    
    signals = []
    
    for i in range(MA_PERIOD, len(weekly_df)):
        curr = weekly_df.iloc[i]
        prev = weekly_df.iloc[i - 1]
        
        if pd.isna(curr["bb_lower"]) or pd.isna(curr["ema20"]):
            continue
        
        is_green = curr["close"] > curr["open"]
        if not is_green:
            continue
        
        opens_below_bb = curr["open"] < curr["bb_lower"]
        if not opens_below_bb:
            continue
        
        bigger_body = curr["body"] > prev["body"]
        if not bigger_body:
            continue
        
        signals.append({
            "signal_index": i,
            "signal_date": curr["week_start"],
            "signal_week_end": curr["week_end"],
            "signal_close": curr["close"],
            "signal_open": curr["open"],
            "bb_lower": curr["bb_lower"],
            "ema20_at_signal": curr["ema20"],
        })
    
    return pd.DataFrame(signals) if signals else pd.DataFrame()


def calculate_trade(signal_row: Dict, df: pd.DataFrame, symbol: str, weekly_df: pd.DataFrame) -> Optional[Dict]:
    signal_index = signal_row["signal_index"]
    signal_week_end = signal_row["signal_week_end"]
    
    entry_candidates = df[df["date"] > signal_week_end].head(1)
    if len(entry_candidates) == 0:
        return None
    
    entry_actual = entry_candidates.iloc[0]
    entry_price = entry_actual["open"]
    entry_date = entry_actual["date"]
    
    sl_price = entry_price * (1 - FIXED_SL_PCT / 100)
    
    entry_week_idx = None
    for idx in range(signal_index + 1, len(weekly_df)):
        week = weekly_df.iloc[idx]
        if week["week_start"] <= entry_date <= week["week_end"]:
            entry_week_idx = idx
            break
    
    if entry_week_idx is None:
        return None
    
    subsequent_weekly = weekly_df.iloc[entry_week_idx + 1:].copy()
    if len(subsequent_weekly) == 0:
        return None
    
    exit_price = None
    exit_date = None
    hit_sl = False
    exit_reason = "NOT_HIT"
    weeks_held = 0
    
    for idx in subsequent_weekly.index:
        week = weekly_df.loc[idx]
        weeks_held += 1
        tp_level = week["ema20"]
        
        if pd.isna(tp_level):
            continue
        
        sl_hit = week["low"] <= sl_price
        tp_hit = week["high"] >= tp_level
        
        if sl_hit and tp_hit:
            dist_to_sl = abs(week["open"] - sl_price)
            dist_to_tp = abs(week["open"] - tp_level)
            
            if dist_to_sl < dist_to_tp:
                exit_price = sl_price
                exit_date = week["week_end"]
                hit_sl = True
                exit_reason = "SL_HIT"
            else:
                exit_price = tp_level
                exit_date = week["week_end"]
                exit_reason = "TP_HIT"
            break
        elif sl_hit:
            exit_price = sl_price
            exit_date = week["week_end"]
            hit_sl = True
            exit_reason = "SL_HIT"
            break
        elif tp_hit:
            exit_price = tp_level
            exit_date = week["week_end"]
            exit_reason = "TP_HIT"
            break
    
    if exit_price is None:
        last_week = subsequent_weekly.iloc[-1]
        exit_price = last_week["close"]
        exit_date = last_week["week_end"]
        exit_reason = "DATA_END"
    
    if exit_date is None or exit_price is None:
        return None
    
    gross_return = (exit_price - entry_price) / entry_price
    transaction_costs = TRANSACTION_COST_PCT / 100
    net_return = gross_return - transaction_costs
    
    return {
        "symbol": symbol,
        "signal_date": signal_row["signal_date"],
        "entry_date": entry_date,
        "exit_date": exit_date,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "sl_price": sl_price,
        "net_return_pct": net_return * 100,
        "gross_return_pct": gross_return * 100,
        "exit_reason": exit_reason,
        "hit_stop_loss": hit_sl,
        "days_held": (exit_date - entry_date).days,
        "weeks_held": weeks_held,
        "year": entry_date.year,
    }


def analyze_basket_detailed(basket_name: str, basket_path: str) -> Tuple[pd.DataFrame, Dict]:
    symbols = load_basket(basket_path)
    
    symbol_data = {}
    for symbol in symbols:
        df = load_ohlc_data(symbol)
        if df is not None and len(df) >= 100:
            weekly_df = get_weekly_candles(df)
            if len(weekly_df) >= 25:
                symbol_data[symbol] = (df, weekly_df)
    
    all_trades = []
    
    for symbol in symbols:
        if symbol not in symbol_data:
            continue
        
        df, weekly_df = symbol_data[symbol]
        signals_df = identify_signals(weekly_df)
        
        if len(signals_df) == 0:
            continue
        
        last_exit_date = None
        
        for _, signal_row in signals_df.iterrows():
            if last_exit_date is not None and signal_row["signal_date"] < last_exit_date:
                continue
            
            trade = calculate_trade(signal_row.to_dict(), df, symbol, weekly_df)
            if trade:
                all_trades.append(trade)
                last_exit_date = trade["exit_date"]
    
    if not all_trades:
        return pd.DataFrame(), {}
    
    trades_df = pd.DataFrame(all_trades)
    
    # Calculate stats
    total_trades = len(trades_df)
    winners = trades_df[trades_df["net_return_pct"] > 0]
    losers = trades_df[trades_df["net_return_pct"] <= 0]
    
    gross_profits = winners["net_return_pct"].sum()
    gross_losses = abs(losers["net_return_pct"].sum())
    profit_factor = gross_profits / gross_losses if gross_losses > 0 else float('inf')
    
    stats = {
        "basket": basket_name,
        "total_trades": total_trades,
        "winners": len(winners),
        "losers": len(losers),
        "win_rate": len(winners) / total_trades * 100,
        "avg_return": trades_df["net_return_pct"].mean(),
        "median_return": trades_df["net_return_pct"].median(),
        "std_return": trades_df["net_return_pct"].std(),
        "total_return": trades_df["net_return_pct"].sum(),
        "profit_factor": profit_factor,
        "avg_winner": winners["net_return_pct"].mean() if len(winners) > 0 else 0,
        "avg_loser": losers["net_return_pct"].mean() if len(losers) > 0 else 0,
        "best_trade": trades_df["net_return_pct"].max(),
        "worst_trade": trades_df["net_return_pct"].min(),
        "avg_days": trades_df["days_held"].mean(),
        "avg_weeks": trades_df["weeks_held"].mean(),
    }
    
    return trades_df, stats


def print_distribution(trades_df: pd.DataFrame, basket_name: str):
    """Print detailed distribution analysis"""
    returns = trades_df["net_return_pct"]
    
    print(f"\n{'═'*80}")
    print(f"RETURN DISTRIBUTION: {basket_name.upper()} BASKET")
    print(f"{'═'*80}")
    
    print(f"\n📊 Summary Statistics:")
    print(f"   Count:    {len(returns)}")
    print(f"   Mean:     {returns.mean():+.2f}%")
    print(f"   Median:   {returns.median():+.2f}%")
    print(f"   Std Dev:  {returns.std():.2f}%")
    print(f"   Min:      {returns.min():+.2f}%")
    print(f"   Max:      {returns.max():+.2f}%")
    
    print(f"\n📈 Percentiles:")
    for p in [5, 10, 25, 50, 75, 90, 95]:
        print(f"   P{p:2d}: {np.percentile(returns, p):+7.2f}%")
    
    print(f"\n📦 Return Buckets:")
    buckets = [
        (-100, -20, "Heavy Loss (< -20%)    "),
        (-20, -10, "Moderate Loss (-20/-10)"),
        (-10, -5, "Small Loss (-10/-5)    "),
        (-5, 0, "Minor Loss (-5/0)      "),
        (0, 5, "Minor Gain (0/5)       "),
        (5, 10, "Small Gain (5/10)      "),
        (10, 20, "Moderate Gain (10/20)  "),
        (20, 50, "Good Gain (20/50)      "),
        (50, 100, "Great Gain (50/100)    "),
        (100, 500, "Exceptional (>100%)    "),
    ]
    
    total = len(returns)
    for low, high, label in buckets:
        count = len(returns[(returns >= low) & (returns < high)])
        pct = count / total * 100
        bar = "█" * int(pct / 2)
        if count > 0:
            print(f"   {label} | {count:4} ({pct:5.1f}%) {bar}")
    
    # Year-wise performance
    print(f"\n📅 Year-wise Performance:")
    yearly = trades_df.groupby("year").agg({
        "net_return_pct": ["count", "mean", "median", "sum"],
        "hit_stop_loss": "sum"
    })
    yearly.columns = ["Trades", "Avg%", "Med%", "Total%", "SL_Hits"]
    yearly["Win%"] = ((yearly["Trades"] - yearly["SL_Hits"]) / yearly["Trades"] * 100).round(1)
    print(yearly.round(2).to_string())
    
    # Exit reason breakdown
    print(f"\n🚪 Exit Reasons:")
    exit_counts = trades_df["exit_reason"].value_counts()
    for reason, count in exit_counts.items():
        pct = count / total * 100
        avg_ret = trades_df[trades_df["exit_reason"] == reason]["net_return_pct"].mean()
        print(f"   {reason:10}: {count:4} ({pct:5.1f}%) | Avg Return: {avg_ret:+.2f}%")
    
    # Top and bottom symbols
    print(f"\n🏆 Top 10 Symbols:")
    symbol_perf = trades_df.groupby("symbol")["net_return_pct"].agg(["count", "mean", "sum"])
    symbol_perf.columns = ["Trades", "Avg%", "Total%"]
    print(symbol_perf.sort_values("Total%", ascending=False).head(10).round(2).to_string())
    
    print(f"\n📉 Bottom 10 Symbols:")
    print(symbol_perf.sort_values("Total%", ascending=True).head(10).round(2).to_string())


def print_critique():
    """Print strategy critique and potential flaws"""
    print(f"\n{'═'*80}")
    print(f"⚠️  STRATEGY CRITIQUE & POTENTIAL FLAWS")
    print(f"{'═'*80}")
    
    critique_points = [
        ("1. LOOK-AHEAD BIAS IN BB CALCULATION", 
         """The Bollinger Band uses CLOSE price for calculation, but we check if OPEN < BB lower.
   At the time of the open, we don't know the close yet. 
   
   IMPACT: In real trading, you can't know the BB value at market open because it
   depends on the close. We're using the completed week's BB, not a real-time value.
   
   FIX: Use previous week's BB value for signal detection, or calculate BB at week open."""),
        
        ("2. FRIDAY CLOSE ASSUMPTION",
         """We assume exit happens at Friday close when TP/SL is hit during the week.
   In reality, you'd exit when price actually hits the level intraweek.
   
   IMPACT: Overestimates returns when price hits TP early in week then reverses.
   Underestimates returns when price gaps through TP.
   
   FIX: Use daily data to find exact exit day within the week."""),
        
        ("3. INTRAWEEK SL/TP AMBIGUITY",
         """When both SL and TP are hit in same week, we use distance from open as proxy.
   This is a heuristic, not actual price sequence.
   
   IMPACT: ~5-10% of trades may have wrong exit assignment.
   
   FIX: Use intraweek (daily) data to determine actual sequence."""),
        
        ("4. SURVIVORSHIP BIAS",
         """We're testing on stocks that exist TODAY in the baskets.
   Stocks that went bankrupt, delisted, or were removed aren't included.
   
   IMPACT: Overstates historical returns. Failed companies would have triggered
   more -20% stop losses.
   
   FIX: Use point-in-time basket composition for each year."""),
        
        ("5. DYNAMIC TP CAN MOVE AGAINST YOU",
         """The EMA 20 TP target moves down when price drops further.
   If stock keeps falling, the TP moves lower, making it easier to hit.
   
   IMPACT: Can lock in small gains when stock reverses just slightly.
   Not necessarily bad, but different from a fixed target.
   
   OBSERVATION: This is actually intentional - mean reversion target."""),
        
        ("6. FIXED 20% SL IS ARBITRARY",
         """20% is a round number with no theoretical basis.
   Different volatility regimes may need different SL levels.
   
   IMPACT: May be too tight for volatile stocks, too loose for stable ones.
   
   FIX: Use ATR-based dynamic stop loss."""),
        
        ("7. NO POSITION SIZING / CAPITAL CONSTRAINTS",
         """Each trade is independent - no limit on concurrent positions.
   Real trading has capital limits.
   
   IMPACT: In 2008/2020 crashes, dozens of signals fire simultaneously.
   Can't take all trades with real capital.
   
   FIX: Add position sizing and concurrent position limits."""),
        
        ("8. TRANSACTION COSTS MAY BE UNDERSTATED",
         """0.37% total (0.185% each way) assumes good execution.
   Doesn't account for slippage, impact cost on large orders, or gap risk.
   
   IMPACT: For 20% SL hit, 0.37% is negligible.
   For 3-5% gains, 0.37% is 7-12% of profits.
   
   FIX: Add slippage estimate (0.1-0.3% for large caps)."""),
        
        ("9. OVERLAP PROTECTION MAY MISS GOOD SIGNALS",
         """If a trade takes 8 weeks, we skip all signals in between.
   A better signal during that period is missed.
   
   IMPACT: Reduces trade count, may miss some winners.
   
   ALTERNATIVE: Allow overlapping positions with position limits."""),
        
        ("10. BB PERIOD MISMATCH WITH EMA",
         """BB uses 20-period SMA for std calculation, but TP uses 20-period EMA.
   These are slightly different values.
   
   IMPACT: Minor - EMA is more responsive, which is fine for TP target.
   
   OBSERVATION: Intentional design choice, not necessarily a flaw."""),
    ]
    
    for title, description in critique_points:
        print(f"\n{title}")
        print(f"   {'-'*70}")
        for line in description.strip().split('\n'):
            print(f"   {line}")
    
    print(f"\n{'─'*80}")
    print(f"SEVERITY ASSESSMENT:")
    print(f"{'─'*80}")
    print(f"   🔴 CRITICAL (materially affects results):")
    print(f"      - #1 Look-ahead bias in BB calculation")
    print(f"      - #4 Survivorship bias")
    print(f"")
    print(f"   🟡 MODERATE (affects accuracy):")
    print(f"      - #2 Friday close assumption")
    print(f"      - #3 Intraweek SL/TP ambiguity")
    print(f"      - #7 No position sizing")
    print(f"")
    print(f"   🟢 MINOR (theoretical concerns):")
    print(f"      - #5, #6, #8, #9, #10")


def main():
    print(f"\n🔬 EMA 20 / 2.0SD STRATEGY - DETAILED ANALYSIS")
    print(f"{'═'*80}")
    print(f"\nStrategy Parameters:")
    print(f"   • MA Type: EMA 20")
    print(f"   • Entry: Opens below BB 2.0 SD + Green candle + Bigger body")
    print(f"   • Exit TP: Weekly high >= Dynamic EMA 20")
    print(f"   • Exit SL: Fixed -20%")
    print(f"   • Transaction Cost: 0.37%")
    
    # Analyze both baskets
    baskets = [
        ("large", "data/baskets/basket_large.txt"),
        ("mid", "data/baskets/basket_mid.txt"),
    ]
    
    all_stats = []
    
    for basket_name, basket_path in baskets:
        print(f"\n📊 Analyzing {basket_name.upper()} basket...")
        trades_df, stats = analyze_basket_detailed(basket_name, basket_path)
        
        if len(trades_df) > 0:
            all_stats.append(stats)
            print_distribution(trades_df, basket_name)
            
            # Save trades
            output_path = f"reports/ema20_2sd_{basket_name}_trades.csv"
            trades_df.to_csv(output_path, index=False)
            print(f"\n💾 Saved: {output_path}")
    
    # Summary comparison
    print(f"\n{'═'*80}")
    print(f"SUMMARY COMPARISON")
    print(f"{'═'*80}\n")
    
    print(f"{'Metric':<25} | {'LARGE':>12} | {'MID':>12}")
    print(f"{'-'*25}-+-{'-'*12}-+-{'-'*12}")
    
    metrics = [
        ("Total Trades", "total_trades", "d"),
        ("Win Rate %", "win_rate", ".1f"),
        ("Avg Return %", "avg_return", "+.2f"),
        ("Median Return %", "median_return", "+.2f"),
        ("Std Dev %", "std_return", ".2f"),
        ("Total Return %", "total_return", ".1f"),
        ("Profit Factor", "profit_factor", ".2f"),
        ("Avg Winner %", "avg_winner", "+.2f"),
        ("Avg Loser %", "avg_loser", "+.2f"),
        ("Best Trade %", "best_trade", "+.2f"),
        ("Worst Trade %", "worst_trade", "+.2f"),
        ("Avg Days Held", "avg_days", ".1f"),
    ]
    
    for label, key, fmt in metrics:
        large_val = all_stats[0].get(key, 0)
        mid_val = all_stats[1].get(key, 0)
        large_formatted = format(large_val, fmt)
        mid_formatted = format(mid_val, fmt)
        print(f"{label:<25} | {large_formatted:>12} | {mid_formatted:>12}")
    
    # Print critique
    print_critique()


if __name__ == "__main__":
    main()


# ========== FROM: test_ema20_2sd_sl_variants.py ==========

#!/usr/bin/env python3
"""
EMA 20 / 2.0SD Strategy - SL Variants Comparison
Tests 10%, 20%, and 25% stop loss levels
Uses daily data for exact entry/exit
"""

import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Configuration
MA_TYPE = "EMA"
MA_PERIOD = 20
BB_SD = 2.0
TRANSACTION_COST = 0.0037  # 0.37% total (0.185% per leg)

SL_VARIANTS = [0.10, 0.20, 0.25, 0.30, None]  # 10%, 20%, 25%, 30%, No SL

CACHE_DIR = Path("data/cache/dhan/daily")

# Combined Large + Mid baskets
ALL_SYMBOLS = [
    # Large
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "BHARTIARTL", "INFY", "SBIN",
    "ITC", "HINDUNILVR", "LT", "BAJFINANCE", "HCLTECH", "MARUTI", "SUNPHARMA",
    "ADANIENT", "KOTAKBANK", "AXISBANK", "ONGC", "TITAN", "NTPC", "ADANIPORTS",
    "ULTRACEMCO", "ASIANPAINT", "COALINDIA", "BAJAJFINSV", "TATAMOTORS",
    "POWERGRID", "NESTLEIND", "M&M", "JSWSTEEL", "TATASTEEL", "WIPRO",
    "HDFCLIFE", "TECHM", "GRASIM", "DRREDDY", "BRITANNIA", "HINDALCO",
    "BAJAJ-AUTO", "INDUSINDBK", "CIPLA", "SBILIFE", "DIVISLAB", "EICHERMOT",
    "BPCL", "TATACONSUM", "APOLLOHOSP", "HEROMOTOCO", "SHRIRAMFIN", "VEDL",
    "ZOMATO", "ADANIGREEN", "DABUR", "INDIGO", "GODREJCP", "SIEMENS",
    "TRENT", "DLF", "BEL", "BANKBARODA", "IOC", "PNB", "HAVELLS", "ABB",
    "JIOFIN", "AMBUJACEM", "GAIL", "PIDILITIND", "CHOLAFIN", "CANBK",
    "TATAPOWER", "PFC", "RECLTD", "HAL", "MANKIND", "TORNTPHARM", "VBL",
    "UNIONBANK", "ATGL", "ICICIPRULI", "ZYDUSLIFE", "INDIANB", "LODHA",
    "POLYCAB", "NHPC", "IRFC", "JSWENERGY", "NAUKRI", "COLPAL", "CGPOWER",
    "BOSCHLTD", "PERSISTENT", "INDUSTOWER", "ICICIGI", "JINDALSTEL", "SRF",
    "IOB", "IDBI", "MAXHEALTH", "HDFCAMC", "MOTHERSON", "INDHOTEL", "TMPV",
    # Mid
    "ADANIPOWER", "MCDOWELL-N", "IRCTC", "PIIND", "NMDC", "PAGEIND", "ACC",
    "MUTHOOTFIN", "CONCOR", "AUROPHARMA", "CUMMINSIND", "LICHSGFIN",
    "OBEROIRLTY", "TIINDIA", "FEDERALBNK", "HINDPETRO", "LUPIN", "PETRONET",
    "BALKRISIND", "GODREJPROP", "LTIM", "ASTRAL", "SOLARINDS", "GMRAIRPORT",
    "COFORGE", "BHARATFORG", "TATACOMM", "DELHIVERY", "BHEL", "PRESTIGE",
    "VOLTAS", "APLAPOLLO", "MARICO", "SUPREMEIND", "MPHASIS", "BIOCON",
    "SAIL", "ALKEM", "SYNGENE", "IDFCFIRSTB", "LALPATHLAB", "ABCAPITAL",
    "TVSMOTOR", "IDEA", "UBL", "MRF", "BANDHANBNK", "LTTS", "KPITTECH",
    "SONACOMS", "AUBANK", "AJANTPHARM", "PATANJALI", "ESCORTS", "LAURUSLABS",
    "APOLLOTYRE", "NATIONALUM", "PEL", "UPL", "OFSS", "MFSL", "CROMPTON",
    "JKCEMENT", "ASHOKLEY", "L&TFH", "FORTIS", "YESBANK", "COROMANDEL",
    "HONAUT", "SUNTV", "DEEPAKNTR", "TATAELXSI", "IGL", "KANSAINER",
    "CENTRALBK", "NIACL", "SCHAEFFLER", "PHOENIXLTD", "GICRE", "LINDEINDIA",
    "NAM-INDIA", "KEI", "THERMAX", "KALYANKJIL", "ABFRL", "M&MFIN",
    "CRISIL", "BANKINDIA", "RAMCOCEM", "ZEEL", "EXIDEIND", "BSE",
    "SUNDARMFIN", "CLEAN", "SUZLON", "OIL", "TATATECH", "JSWINFRA", "LLOYDSME",
    "FACT", "POONAWALLA", "RADICO", "MOTILALOFS", "HINDCOPPER", "MAHABANK",
    "KAJARIACER", "GLAXO", "METROBRAND", "RELAXO", "SJVN", "IRB", "MRPL",
    "STARHEALTH", "DMART", "BERGEPAINT", "RAYMOND", "BATAINDIA", "POLICYBZR",
    "RBLBANK", "PNBHOUSING", "NLCINDIA", "KAYNES", "ITI", "NATCOPHARM",
    "CUB", "RVNL", "GUJGASLTD", "MSUMI", "AIAENG", "JSL", "HFCL", "NBCC",
    "HUDCO", "CARBORUNIV", "JBCHEPHARM", "BLUEDART", "PGHH", "ZFCVINDIA",
    "IREDA", "INOXWIND", "CDSL", "CREDITACC", "COCHINSHIP", "CESC", "ENDURANCE",
    "CYIENT", "FIVESTAR", "FSL", "TIMKEN", "IDFC", "SKFINDIA", "GODREJIND",
    "OLECTRA", "KPRMILL", "3MINDIA", "SHYAMMETL", "EIDPARRY", "GSFC", "GRINDWELL",
    "GNFC", "EMAMILTD", "GLENMARK", "GRAPHITE", "ZENSARTECH", "LUXIND",
    "BRIGADE", "CHOLAHLDNG", "HAPPSTMNDS", "APTUS", "SUVENPHAR", "360ONE",
    "BDL", "ATUL", "JYOTHYLAB", "SUMICHEM", "NUVAMA", "SOBHA", "LXCHEM",
    "TRITURBINE", "HEXT", "ACE", "FINCABLES", "BLUESTARCO", "MGL", "INDIAMART",
    "RHIM", "ELGIEQUIP", "RATNAMANI", "VTL", "CHALET", "REDINGTON", "IEX",
    "APARINDS", "GESHIP", "NEULANDLAB", "TRIVENI", "FINPIPE", "WELSPUNLIV",
    "KRBL", "NYKAA", "KIMS", "ANURAS", "BALAMINES", "AFFLE", "ABSLAMC",
    "ASAHIINDIA", "JUBLPHARMA", "SCHNEIDER", "POWERMECH", "CCL", "DATAPATTNS",
    "MANAPPURAM", "PGHL", "AWL", "BIRLACORPN", "VGUARD", "GPIL", "AMBER",
    "SWANENERGY"
]


def load_daily_data(symbol: str) -> pd.DataFrame:
    """Load daily OHLC data for a symbol"""
    pattern = f"dhan_*_{symbol}_1d.csv"
    matches = list(CACHE_DIR.glob(pattern))
    
    if not matches:
        return pd.DataFrame()
    
    file_path = matches[0]
    df = pd.read_csv(file_path)
    if 'time' in df.columns:
        df = df.rename(columns={'time': 'date'})
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    return df


def resample_to_weekly(daily_df: pd.DataFrame) -> pd.DataFrame:
    """Resample daily data to weekly OHLC"""
    df = daily_df.copy()
    df = df.set_index('date')
    
    weekly = df.resample('W-FRI').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    
    weekly = weekly.reset_index()
    return weekly


def calculate_indicators(weekly_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate BB and EMA on weekly data"""
    df = weekly_df.copy()
    
    df['sma20'] = df['close'].rolling(20).mean()
    df['std20'] = df['close'].rolling(20).std()
    df['bb_lower'] = df['sma20'] - BB_SD * df['std20']
    df['ema20'] = df['close'].ewm(span=MA_PERIOD, adjust=False).mean()
    
    return df


def find_entry_day(daily_df: pd.DataFrame, signal_week_end: pd.Timestamp) -> tuple:
    """Find the first trading day after signal week end"""
    next_days = daily_df[daily_df['date'] > signal_week_end].head(5)
    
    if len(next_days) == 0:
        return None, None
    
    entry_row = next_days.iloc[0]
    return entry_row['date'], entry_row['open']


def find_exit_day_daily(daily_df: pd.DataFrame, weekly_df: pd.DataFrame,
                        entry_date: pd.Timestamp, entry_price: float, 
                        sl_price: float) -> tuple:
    """Find exact exit day using daily data with weekly EMA target"""
    df = daily_df[daily_df['date'] >= entry_date].copy()
    
    if len(df) < 2:
        return None, None, "DATA_END"
    
    df = df.iloc[1:]  # Skip entry day
    
    for _, row in df.iterrows():
        day_date = row['date']
        
        # Find weekly EMA for this day (use previous week's value)
        week_mask = weekly_df['date'] >= day_date
        if not week_mask.any():
            weekly_ema = weekly_df['ema20'].iloc[-1]
        else:
            week_idx = weekly_df[week_mask].index[0]
            if week_idx > 0:
                weekly_ema = weekly_df.iloc[week_idx - 1]['ema20']
            else:
                weekly_ema = weekly_df.iloc[0]['ema20']
        
        if pd.isna(weekly_ema):
            continue
        
        # Check SL first (only if SL is set)
        if sl_price is not None and row['low'] <= sl_price:
            return row['date'], sl_price, "SL_HIT"
        
        # Check TP
        if row['high'] >= weekly_ema:
            return row['date'], weekly_ema, "TP_HIT"
    
    last_row = df.iloc[-1] if len(df) > 0 else daily_df.iloc[-1]
    return last_row['date'], last_row['close'], "DATA_END"


def analyze_with_sl(sl_pct: float) -> dict:
    """Analyze all symbols with a specific SL percentage"""
    all_trades = []
    
    for symbol in list(set(ALL_SYMBOLS)):
        daily_df = load_daily_data(symbol)
        if len(daily_df) < 100:
            continue
        
        weekly_df = resample_to_weekly(daily_df)
        if len(weekly_df) < 25:
            continue
        
        weekly_df = calculate_indicators(weekly_df)
        
        last_exit_date = None
        
        for i in range(2, len(weekly_df) - 1):
            row = weekly_df.iloc[i]
            prev_row = weekly_df.iloc[i - 1]
            
            if last_exit_date and row['date'] <= last_exit_date:
                continue
            
            if pd.isna(row['bb_lower']) or pd.isna(row['ema20']):
                continue
            
            is_green = row['close'] > row['open']
            opens_below_bb = row['open'] < row['bb_lower']
            body = abs(row['close'] - row['open'])
            prev_body = abs(prev_row['close'] - prev_row['open'])
            bigger_body = body > prev_body
            
            if is_green and opens_below_bb and bigger_body:
                entry_date, entry_price = find_entry_day(daily_df, row['date'])
                
                if entry_date is None or entry_price is None or entry_price <= 0:
                    continue
                
                sl_price = entry_price * (1 - sl_pct) if sl_pct is not None else None
                
                exit_date, exit_price, exit_reason = find_exit_day_daily(
                    daily_df, weekly_df, entry_date, entry_price, sl_price
                )
                
                if exit_date is None or exit_price is None:
                    continue
                
                gross_return = (exit_price - entry_price) / entry_price
                net_return = gross_return - TRANSACTION_COST
                
                all_trades.append({
                    'symbol': symbol,
                    'entry_date': entry_date,
                    'exit_date': exit_date,
                    'exit_reason': exit_reason,
                    'net_return': net_return,
                    'days_held': (exit_date - entry_date).days,
                    'year': entry_date.year
                })
                
                last_exit_date = exit_date
    
    if not all_trades:
        return None
    
    trades_df = pd.DataFrame(all_trades)
    
    # Calculate stats
    total_trades = len(trades_df)
    winners = trades_df[trades_df['net_return'] > 0]
    losers = trades_df[trades_df['net_return'] <= 0]
    
    win_rate = len(winners) / total_trades * 100
    avg_return = trades_df['net_return'].mean() * 100
    median_return = trades_df['net_return'].median() * 100
    total_return = trades_df['net_return'].sum() * 100
    
    gross_profit = winners['net_return'].sum() if len(winners) > 0 else 0
    gross_loss = abs(losers['net_return'].sum()) if len(losers) > 0 else 0.0001
    profit_factor = gross_profit / gross_loss
    
    sl_hits = len(trades_df[trades_df['exit_reason'] == 'SL_HIT'])
    
    return {
        'sl_pct': sl_pct,
        'trades': total_trades,
        'win_rate': win_rate,
        'avg_return': avg_return,
        'median_return': median_return,
        'total_return': total_return,
        'profit_factor': profit_factor,
        'sl_hits': sl_hits,
        'sl_hit_rate': sl_hits / total_trades * 100,
        'avg_winner': winners['net_return'].mean() * 100 if len(winners) > 0 else 0,
        'avg_loser': losers['net_return'].mean() * 100 if len(losers) > 0 else 0,
        'avg_days': trades_df['days_held'].mean(),
        'trades_df': trades_df
    }


def main():
    print("=" * 80)
    print("🔬 EMA 20 / 2.0SD STRATEGY - STOP LOSS VARIANTS COMPARISON")
    print("=" * 80)
    print(f"\nStrategy Parameters:")
    print(f"   • Signal: Weekly green candle + Opens below BB {BB_SD} SD + Bigger body")
    print(f"   • Entry: First trading day after signal week at OPEN")
    print(f"   • Exit TP: Daily HIGH >= Weekly EMA {MA_PERIOD}")
    print(f"   • Transaction Cost: {TRANSACTION_COST:.2%} total (0.185% per leg)")
    print()
    print(f"Testing SL Variants: {[f'{sl*100:.0f}%' if sl else 'No SL' for sl in SL_VARIANTS]}")
    print()
    
    results = []
    
    for sl_pct in SL_VARIANTS:
        sl_label = f"{sl_pct*100:.0f}%" if sl_pct else "No SL"
        print(f"📊 Testing {sl_label} Stop Loss...")
        stats = analyze_with_sl(sl_pct)
        if stats:
            results.append(stats)
    
    print()
    print("=" * 80)
    print("COMPARISON RESULTS")
    print("=" * 80)
    print()
    
    # Header - dynamic based on variants
    headers = [f"{sl*100:.0f}% SL" if sl else "No SL" for sl in SL_VARIANTS]
    header_row = f"{'Metric':<25} |" + "|".join([f"{h:>12}" for h in headers])
    print(header_row)
    print("-" * len(header_row))
    
    # Metrics to display
    metrics = [
        ("Total Trades", "trades", "d"),
        ("Win Rate %", "win_rate", ".1f"),
        ("Profit Factor", "profit_factor", ".2f"),
        ("Avg Return %", "avg_return", "+.2f"),
        ("Median Return %", "median_return", "+.2f"),
        ("Total Return %", "total_return", "+.1f"),
        ("SL Hits", "sl_hits", "d"),
        ("SL Hit Rate %", "sl_hit_rate", ".1f"),
        ("Avg Winner %", "avg_winner", "+.2f"),
        ("Avg Loser %", "avg_loser", "+.2f"),
        ("Avg Days Held", "avg_days", ".1f"),
    ]
    
    for label, key, fmt in metrics:
        vals = [format(r[key], fmt) for r in results]
        row = f"{label:<25} |" + "|".join([f"{v:>12}" for v in vals])
        print(row)
    
    print()
    print("=" * 80)
    print("KEY OBSERVATIONS")
    print("=" * 80)
    
    # Find best
    best_pf = max(results, key=lambda x: x['profit_factor'])
    best_total = max(results, key=lambda x: x['total_return'])
    
    best_pf_label = f"{best_pf['sl_pct']*100:.0f}%" if best_pf['sl_pct'] else "No"
    best_total_label = f"{best_total['sl_pct']*100:.0f}%" if best_total['sl_pct'] else "No"
    
    print(f"""
📈 Best Profit Factor: {best_pf_label} SL (PF: {best_pf['profit_factor']:.2f})
💰 Best Total Return: {best_total_label} SL ({best_total['total_return']:+.1f}%)

🔍 Trade-off Analysis:
   • Tighter SL (10%): More SL hits, smaller losers, lower win rate
   • Wider SL (25-30%): Fewer SL hits, more room to recover
   • No SL: Maximum room to recover, but unlimited downside risk
""")

    # Year-wise comparison for 20% SL
    print("=" * 80)
    print("YEAR-WISE PERFORMANCE (20% SL)")
    print("=" * 80)
    
    sl20_df = results[1]['trades_df']  # 20% is second
    yearly = sl20_df.groupby('year').agg({
        'net_return': ['count', 'mean', 'sum'],
        'exit_reason': lambda x: (x == 'SL_HIT').sum()
    })
    yearly.columns = ['Trades', 'Avg%', 'Total%', 'SL_Hits']
    yearly['Avg%'] = (yearly['Avg%'] * 100).round(2)
    yearly['Total%'] = (yearly['Total%'] * 100).round(1)
    print(yearly.to_string())


if __name__ == "__main__":
    main()


# ========== FROM: test_ema20_5_5_20.py ==========

#!/usr/bin/env python3
"""
Test EMA20 Mean Reversion: 5% drop, 5% TP, 20% SL on Main Basket

Parameters:
- EMA Period: 20
- Entry: Price drops 5% below EMA20
- Take Profit: 5% from entry
- Stop Loss: 20% from entry
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime
from core.loaders import load_many_india


# Configuration
EMA_PERIOD = 20
ENTRY_DROP_PCT = 0.05      # 5% below EMA
TP_PCT = 0.05              # 5% TP from entry
SL_PCT = 0.20              # 20% SL from entry
POSITION_SIZE = 100000     # ₹1L per trade

BASKET_DIR = Path("data/baskets")


def load_basket(basket_name: str) -> list:
    """Load symbols from basket file."""
    basket_file = BASKET_DIR / f"basket_{basket_name}.txt"
    
    if not basket_file.exists():
        print(f"❌ Basket file not found: {basket_file}")
        return []
    
    with open(basket_file, "r") as f:
        symbols = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    
    return symbols


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Calculate EMA."""
    return series.ewm(span=period, adjust=False).mean()


def backtest_symbol(df: pd.DataFrame, symbol: str) -> list:
    """
    Run backtest for single symbol.
    
    Entry: Close drops X% below EMA
    Exit: TP% gain OR SL% loss from entry
    """
    if len(df) < EMA_PERIOD + 10:
        return []
    
    df = df.copy()
    
    # Handle date - could be in index or column
    if "date" not in df.columns:
        df = df.reset_index()
        if "time" in df.columns:
            df = df.rename(columns={"time": "date"})
    
    df = df.sort_values("date").reset_index(drop=True)
    
    # Calculate EMA
    df["ema"] = calculate_ema(df["close"], EMA_PERIOD)
    
    trades = []
    in_position = False
    entry_price = 0
    entry_date = None
    tp_price = 0
    sl_price = 0
    
    for i in range(EMA_PERIOD, len(df)):
        row = df.iloc[i]
        close = row["close"]
        high = row["high"]
        low = row["low"]
        ema = row["ema"]
        date = row["date"]
        
        if not in_position:
            # Entry: Close is X% below EMA
            threshold = ema * (1 - ENTRY_DROP_PCT)
            if close < threshold:
                entry_price = close
                entry_date = date
                tp_price = entry_price * (1 + TP_PCT)
                sl_price = entry_price * (1 - SL_PCT)
                in_position = True
        else:
            # Check TP (using high)
            if high >= tp_price:
                exit_price = tp_price
                pnl_pct = TP_PCT * 100
                pnl_amt = POSITION_SIZE * TP_PCT
                
                trades.append({
                    "symbol": symbol,
                    "entry_date": str(entry_date)[:10],
                    "exit_date": str(date)[:10],
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(exit_price, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "pnl_amt": round(pnl_amt, 2),
                    "exit_reason": "TP",
                })
                in_position = False
                continue
            
            # Check SL (using low)
            if low <= sl_price:
                exit_price = sl_price
                pnl_pct = -SL_PCT * 100
                pnl_amt = -POSITION_SIZE * SL_PCT
                
                trades.append({
                    "symbol": symbol,
                    "entry_date": str(entry_date)[:10],
                    "exit_date": str(date)[:10],
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(exit_price, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "pnl_amt": round(pnl_amt, 2),
                    "exit_reason": "SL",
                })
                in_position = False
    
    return trades


def main():
    print("=" * 80)
    print(f"EMA{EMA_PERIOD} MEAN REVERSION TEST")
    print(f"Entry: {ENTRY_DROP_PCT*100:.0f}% below EMA | TP: {TP_PCT*100:.0f}% | SL: {SL_PCT*100:.0f}%")
    print("=" * 80)
    
    # Load main basket
    basket_name = "main"
    symbols = load_basket(basket_name)
    
    if not symbols:
        print("No symbols in basket!")
        return
    
    print(f"\n📊 Basket: {basket_name.upper()} ({len(symbols)} symbols)")
    
    # Load data
    print("Loading data from cache...")
    data = load_many_india(symbols, interval="1d", use_cache_only=True)
    print(f"✅ Loaded data for {len(data)} symbols")
    
    # Run backtest
    all_trades = []
    symbols_with_trades = 0
    
    for symbol, df in data.items():
        trades = backtest_symbol(df, symbol)
        if trades:
            all_trades.extend(trades)
            symbols_with_trades += 1
    
    if not all_trades:
        print("❌ No trades found")
        return
    
    # Create DataFrame
    df_trades = pd.DataFrame(all_trades)
    
    # Calculate stats
    total_trades = len(df_trades)
    wins = df_trades[df_trades["pnl_pct"] > 0]
    losses = df_trades[df_trades["pnl_pct"] <= 0]
    
    win_rate = len(wins) / total_trades * 100
    
    gross_profit = wins["pnl_amt"].sum() if len(wins) > 0 else 0
    gross_loss = abs(losses["pnl_amt"].sum()) if len(losses) > 0 else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    total_pnl = df_trades["pnl_amt"].sum()
    
    tp_exits = len(df_trades[df_trades["exit_reason"] == "TP"])
    sl_exits = len(df_trades[df_trades["exit_reason"] == "SL"])
    
    # Print results
    print(f"\n{'='*80}")
    print(f"RESULTS: {basket_name.upper()}")
    print(f"{'='*80}")
    print(f"Total Trades:     {total_trades:,}")
    print(f"Symbols Traded:   {symbols_with_trades}")
    print(f"Win Rate:         {win_rate:.1f}%")
    print(f"Profit Factor:    {profit_factor:.2f}")
    print(f"")
    print(f"Exit Distribution:")
    print(f"  TP ({TP_PCT*100:.0f}%):  {tp_exits} ({tp_exits/total_trades*100:.1f}%)")
    print(f"  SL ({SL_PCT*100:.0f}%):  {sl_exits} ({sl_exits/total_trades*100:.1f}%)")
    print(f"")
    print(f"Total P&L:        ₹{total_pnl:,.0f}")
    print(f"Per Trade P&L:    ₹{total_pnl/total_trades:,.0f}")
    
    # Top performers
    print(f"\n📈 TOP 5 WINNING TRADES:")
    top_wins = df_trades.nlargest(5, "pnl_pct")
    for _, t in top_wins.iterrows():
        print(f"   {t['symbol']}: +{t['pnl_pct']:.1f}% | ₹{t['pnl_amt']:,.0f}")
    
    print(f"\n📉 WORST 5 TRADES:")
    worst = df_trades.nsmallest(5, "pnl_pct")
    for _, t in worst.iterrows():
        print(f"   {t['symbol']}: {t['pnl_pct']:.1f}% | ₹{t['pnl_amt']:,.0f}")
    
    # Monthly breakdown
    print(f"\n📅 MONTHLY BREAKDOWN (last 12):")
    df_trades["month"] = pd.to_datetime(df_trades["entry_date"]).dt.to_period("M")
    monthly = df_trades.groupby("month").agg({
        "pnl_amt": ["count", "sum"],
    })
    monthly.columns = ["trades", "pnl"]
    print(monthly.tail(12).to_string())
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
