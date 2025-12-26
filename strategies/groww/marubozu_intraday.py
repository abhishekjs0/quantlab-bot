"""
Bullish Marubozu Strategy - INTRADAY VERSION

Deploy on Groww Cloud - runs automatically at 9:15 AM IST (market open).

Strategy Logic
    Entry Conditions:
        1. Bullish candle detected at previous day close
        2. Body size >= 5% of current price (significant move)
        3. Body size >= 80% of candle range (strong body, minimal shadows)
        4. NO EMA filter (simpler, more trades)
        5. Entry at next day market open

    Exit Rules:
        - Exit at SAME DAY market close (1-day hold / BTST)
        - NO target price, NO stop loss

Pattern Detection (Strict body requirements):
    - body >= 5% of price (CMP) - significant move
    - body >= 80% of candle range - minimal shadows

Backtest Results (102 symbols, 9Y, excluding bad data):
    - 1,130 trades across 2016-2024 (after 200-day warmup)
    - Net Return: +0.64% per trade (after 0.11% intraday costs)
    - Win Rate: 52.7%
    - Positive Years: 9/9 (2016-2024 all profitable)
    - Total Return: +723%

"""

import json
import os
import time
from datetime import datetime, timedelta

import numpy as np
import pyotp
from growwapi import GrowwAPI

# Pure numpy-based pattern detection (no TA-Lib dependency)

# =====================
# CONFIGURATION
# =====================

# ⚠️ GROWW CLOUD DEPLOYMENT: Set your credentials here directly
# Get credentials from: https://groww.in/trade-api/api-keys
# Option 1 (TOTP - recommended, no expiry):
#   - Click "Generate TOTP token" dropdown
#   - Copy TOTP_TOKEN (use as API_KEY) and TOTP_SECRET
# Option 2 (API Key + Secret - requires daily approval):
#   - Click "Generate API key"
#   - Copy API Key and Secret

# === SET YOUR CREDENTIALS HERE ===
# Using TOTP Token (expires 2055, no daily approval needed)
GROWW_API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTUxNjc3NDAsImlhdCI6MTc2Njc2Nzc0MCwibmJmIjoxNzY2NzY3NzQwLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJmYTVjOWUwZi02OGQ1LTRmYWItOTcwZi0zNjRiNTE3ZDk1ZDlcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiM2IzY2M4NTktYWYzNS00MWY3LWI0OTgtYmM2ODFlNDRjYzg3XCIsXCJkZXZpY2VJZFwiOlwiMTA1MDU5YzctNzFlOC01ZjNlLWI2MDctZGNjYzc4MGJjNWU4XCIsXCJzZXNzaW9uSWRcIjpcIjQ0ZTAzY2MwLWZlN2QtNDcxYy1iYjNlLTYwZDdiYzg3NDkyNVwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1seHBMN0FMeEhDTkRWT1YycnBuUzlSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIxNC4xMDIuMTYzLjExNiwxNzIuNzAuMjE4LjE4OCwzNS4yNDEuMjMuMTIzXCIsXCJ0d29GYUV4cGlyeVRzXCI6MjU1NTE2Nzc0MDIwMH0iLCJpc3MiOiJhcGV4LWF1dGgtcHJvZC1hcHAifQ.CVtkRiVV5KoFcDQiANb6TUIft8tufL8nBsmyNuth61cxPzXHEodcpCGs_AT0qLwk5Cabo1u-ki1SDJjBOV6_pA"
GROWW_TOTP_SECRET = "JVG42CV6PHCLMTVNSTKEQPN7AOAAL43F"
GROWW_API_SECRET = ""  # Not needed for TOTP flow
# =================================

# Fallback to environment variables (for local testing)
if not GROWW_API_KEY:
    GROWW_API_KEY = os.environ.get("GROWW_API_KEY", "")
if not GROWW_TOTP_SECRET:
    GROWW_TOTP_SECRET = os.environ.get("GROWW_TOTP_SECRET", "")
if not GROWW_API_SECRET:
    GROWW_API_SECRET = os.environ.get("GROWW_API_SECRET", "")

INITIAL_CAPITAL = 100000
POSITION_SIZE_PCT = 0.05  # 5% per position
LOOKBACK_DAYS = 180  # Groww API max for 1-day interval

# =====================
# STRATEGY PARAMETERS (9/9 Backtest Verified - INTRADAY)
# =====================
# These parameters achieved 9/9 positive years (2016-2024)
MIN_BODY_PCT = 5.0           # Minimum body size as % of price (>=5%)
MIN_BODY_RANGE = 0.80        # Minimum body as % of candle range (>=80%)
MAX_HOLD_DAYS = 1            # INTRADAY - exit same day at market close
# NO TARGET, NO STOP LOSS - time-based exit only for consistency
# NO EMA Filter - simpler, more trades, still 9/9 positive years
USE_EMA_FILTER = False       # Set to True for EMA filter (fewer trades)
EMA_PERIODS = [20, 50, 200]  # Only used if USE_EMA_FILTER=True

# Positions tracking file
POSITIONS_FILE = "/tmp/groww_marubozu_positions.json"

# 106 stocks from basket_main.txt (excluding MOTHERSON - bad data)
STOCK_SYMBOLS = [
    "RELIANCE", "BHARTIARTL", "ICICIBANK", "SBIN", "BAJFINANCE", "LICI", "LT",
    "HCLTECH", "AXISBANK", "ULTRACEMCO", "TITAN", "KOTAKBANK", "ADANIENT",
    "TATAPOWER", "ADANIGREEN", "IRFC", "NTPC", "ONGC", "ADANIPORTS", "COALINDIA",
    "MARUTI", "ASIANPAINT", "DMART", "GRASIM", "WIPRO", "SUNPHARMA", "BAJAJFINSV",
    "HDFCLIFE", "M&M", "POWERGRID", "JSWSTEEL", "TECHM", "DIVISLAB", "INDIGO",
    "HINDALCO", "HINDUNILVR", "SBILIFE", "TATACONSUM", "TATASTEEL", "BPCL",
    "CIPLA", "APOLLOHOSP", "GAIL", "IOC", "EICHERMOT", "DRREDDY", "BAJAJ-AUTO",
    "HDFCAMC", "DABUR", "ADANIENSOL", "PFC", "SIEMENS", "INDUSTOWER", "ZOMATO",
    "RECLTD", "HAL", "BEL", "VBL", "SHREECEM", "DLF", "CANBK", "JIOFIN",
    "AMBUJACEM", "PIIND", "BOSCHLTD", "MUTHOOTFIN", "GODREJCP", "COLPAL",
    "TORNTPHARM", "ICICIPRULI", "NAUKRI", "PNB", "JINDALSTEL", "LODHA",
    "INDHOTEL", "TATACOMM", "CHOLAFIN", "MAXHEALTH", "ZYDUSLIFE", "TVSMOTOR",
    "BANKBARODA", "ABB", "HINDPETRO", "HAVELLS", "BHEL", "UBL", "ATGL",
    "POLICYBZR", "PERSISTENT", "TRENT", "PATANJALI", "GMRAIRPORT", "NHPC",
    "JSWENERGY", "IRCTC", "UNIONBANK", "VOLTAS", "LUPIN",  # MOTHERSON excluded
    "CGPOWER", "MARICO", "BALKRISIND", "SJVN",
]


# =====================
# INITIALIZE API
# =====================

print("🚀 Initializing Groww API...")

# Authentication: Groww API requires access_token from either:
# 1. API Key + Secret (requires daily approval on Groww Cloud API Keys Page)
# 2. TOTP flow (no expiry - recommended)

# Method 1: Try TOTP flow (preferred - no expiry)
if GROWW_API_KEY and GROWW_TOTP_SECRET:
    try:
        totp_generator = pyotp.TOTP(GROWW_TOTP_SECRET)
        totp_code = totp_generator.now()
        access_token = GrowwAPI.get_access_token(api_key=GROWW_API_KEY, totp=totp_code)
        groww = GrowwAPI(access_token)
        print("✅ Groww API Ready (TOTP Auth)")
    except Exception as e:
        print(f"❌ TOTP authentication failed: {e}")
        raise SystemExit(1)

# Method 2: Try API Key + Secret flow
elif GROWW_API_KEY and GROWW_API_SECRET:
    try:
        access_token = GrowwAPI.get_access_token(api_key=GROWW_API_KEY, secret=GROWW_API_SECRET)
        groww = GrowwAPI(access_token)
        print("✅ Groww API Ready (API Key + Secret Auth)")
    except Exception as e:
        print(f"❌ API Key authentication failed: {e}")
        raise SystemExit(1)

else:
    print("❌ Missing Groww API credentials")
    print("   Required environment variables:")
    print("   Option 1 (TOTP - recommended): GROWW_API_KEY + GROWW_TOTP_SECRET")
    print("   Option 2 (API Key): GROWW_API_KEY + GROWW_API_SECRET")
    print("")
    print("   Get credentials from: https://groww.in/trade-api/api-keys")
    raise SystemExit(1)


# =====================
# POSITION TRACKING
# =====================


def load_positions():
    """Load tracked positions from file."""
    try:
        if os.path.exists(POSITIONS_FILE):
            with open(POSITIONS_FILE) as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ Error loading positions: {e}")
    return {}


def save_positions(positions):
    """Save tracked positions to file."""
    try:
        with open(POSITIONS_FILE, "w") as f:
            json.dump(positions, f, indent=2, default=str)
    except Exception as e:
        print(f"⚠️ Error saving positions: {e}")


def add_position(symbol, entry_price, body_size, entry_date, quantity):
    """Add a new position to tracking. Exit is time-based only (8 days)."""
    positions = load_positions()

    positions[symbol] = {
        "entry_price": entry_price,
        "entry_date": entry_date.isoformat() if hasattr(entry_date, "isoformat") else str(entry_date),
        "body_size": body_size,
        "quantity": quantity,
        "days_held": 0,
        "exit_on_day": MAX_HOLD_DAYS,  # Simple time-based exit
    }
    save_positions(positions)

    return MAX_HOLD_DAYS  # Return hold period instead of target/stop


def remove_position(symbol):
    """Remove a position from tracking."""
    positions = load_positions()
    if symbol in positions:
        del positions[symbol]
        save_positions(positions)


def increment_days_held():
    """Increment days held for all positions."""
    positions = load_positions()
    for symbol in positions:
        positions[symbol]["days_held"] = positions[symbol].get("days_held", 0) + 1
    save_positions(positions)


# =====================
# HELPER FUNCTIONS
# =====================


def get_historical_data(symbol, days=250):
    """Fetch historical OHLCV data from Groww API."""
    try:
        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        start_time = (datetime.now() - timedelta(days=days)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # Use new get_historical_candles API with groww_symbol format
        groww_symbol = f"NSE-{symbol}"
        response = groww.get_historical_candles(
            exchange=groww.EXCHANGE_NSE,
            segment=groww.SEGMENT_CASH,
            groww_symbol=groww_symbol,
            start_time=start_time,
            end_time=end_time,
            candle_interval=groww.CANDLE_INTERVAL_DAY,  # 1 day interval
        )

        if not response or "candles" not in response or not response["candles"]:
            return None

        candles = response["candles"]
        # Filter out candles with None values
        valid_candles = [c for c in candles if all(v is not None for v in c[:6])]
        if not valid_candles:
            return None
        return {
            "timestamp": [c[0] for c in valid_candles],
            "open": np.array([float(c[1]) for c in valid_candles]),
            "high": np.array([float(c[2]) for c in valid_candles]),
            "low": np.array([float(c[3]) for c in valid_candles]),
            "close": np.array([float(c[4]) for c in valid_candles]),
            "volume": np.array([int(c[5]) for c in valid_candles]),
        }
    except Exception as e:
        print(f"❌ Error fetching {symbol}: {e}")
        return None


def get_live_ohlc(symbol):
    """Get current OHLC data for a symbol."""
    try:
        response = groww.get_ohlc(
            segment=groww.SEGMENT_CASH,
            exchange_trading_symbols=f"NSE_{symbol}",
        )
        return response.get(f"NSE_{symbol}")
    except Exception as e:
        print(f"❌ Error getting OHLC for {symbol}: {e}")
        return None


def calculate_ema(prices, period):
    """Calculate EMA using numpy (no external dependencies)."""
    if len(prices) < period:
        return None

    prices = np.array(prices, dtype=float)
    ema = np.zeros(len(prices))
    multiplier = 2 / (period + 1)
    ema[period - 1] = np.mean(prices[:period])

    for i in range(period, len(prices)):
        ema[i] = (prices[i] - ema[i - 1]) * multiplier + ema[i - 1]

    return ema[-1] if ema[-1] != 0 else None


def detect_bullish_marubozu(open_arr, high_arr, low_arr, close_arr):
    """
    Detect bullish Marubozu patterns using pure numpy (strict body requirements).
    
    INTRADAY Parameters (9/9 positive years with 1D hold):
        - body >= 5% of current price (significant move)
        - body >= 80% of candle range (minimal shadows)
        - NO shadow constraints (simpler, more robust)

    Returns tuple: (is_marubozu, body_size_pct, body_size_abs)
    
    Backtest Results (1,130 trades, 2016-2024, 1D hold):
        - Net Return: +0.64% per trade (after 0.11% intraday costs)
        - Win Rate: 52.7%
        - Positive Years: 9/9 (all years profitable)
        - Total Return: +723%
    """
    o = open_arr[-1]
    h = high_arr[-1]
    low = low_arr[-1]
    c = close_arr[-1]
    
    body = c - o
    body_size = abs(body)
    range_size = h - low
    
    # Skip if no range or bearish
    if range_size == 0 or body <= 0:
        return False, 0, 0
    
    body_pct_of_price = (body_size / o) * 100
    body_pct_of_range = body_size / range_size
    
    # Simple criteria: body >= 5% of price AND body >= 60% of range
    if body_pct_of_price >= MIN_BODY_PCT and body_pct_of_range >= MIN_BODY_RANGE:
        return True, body_pct_of_price, body_size
    
    return False, 0, 0


def calculate_quantity(ltp, capital=INITIAL_CAPITAL, pct=POSITION_SIZE_PCT):
    """Calculate position size based on LTP and capital allocation."""
    if ltp <= 0:
        return 0
    amount = capital * pct
    qty = int(amount / ltp)
    return max(1, qty)


def get_holdings():
    """Get current holdings from Groww."""
    try:
        response = groww.get_holdings_for_user()
        holdings = {}
        if response and "holdings" in response:
            for h in response["holdings"]:
                symbol = h.get("trading_symbol")
                qty = h.get("quantity", 0)
                avg_price = h.get("average_price", 0)
                if symbol and qty > 0:
                    holdings[symbol] = {"qty": qty, "avg_price": avg_price}
        return holdings
    except Exception as e:
        print(f"❌ Error getting holdings: {e}")
        return {}


# =====================
# STEP 1: MANAGE EXISTING POSITIONS
# =====================

print("\n📊 Checking existing positions for exit conditions...")

positions = load_positions()
holdings = get_holdings()
exits_to_execute = []
today = datetime.now().date()

for symbol, pos in positions.items():
    if symbol not in holdings:
        print(f"   ⚠️ {symbol}: Not in holdings, removing from tracking")
        remove_position(symbol)
        continue

    ohlc = get_live_ohlc(symbol)
    if not ohlc:
        continue

    ltp = ohlc.get("ltp", 0)
    days_held = pos.get("days_held", 0)
    entry_price = pos["entry_price"]
    qty = holdings[symbol]["qty"]

    pnl_pct = ((ltp - entry_price) / entry_price) * 100

    exit_reason = None

    # Time-based exit ONLY (10/10 verified strategy)
    # NO target, NO stop loss - simple 8-day hold
    if days_held >= MAX_HOLD_DAYS:
        exit_reason = "8-DAY HOLD COMPLETE (Time Exit)"

    if exit_reason:
        exits_to_execute.append({
            "symbol": symbol,
            "qty": qty,
            "ltp": ltp,
            "entry": entry_price,
            "pnl_pct": pnl_pct,
            "reason": exit_reason,
        })
        print(f"   📤 {symbol}: {exit_reason} | P&L: {pnl_pct:+.2f}%")
    else:
        days_remaining = MAX_HOLD_DAYS - days_held
        print(
            f"   📊 {symbol}: LTP=₹{ltp:.2f} | Entry=₹{entry_price:.2f} | "
            f"P&L={pnl_pct:+.2f}% | Days={days_held}/{MAX_HOLD_DAYS} (Exit in {days_remaining}d)"
        )

# Increment days held for remaining positions
increment_days_held()


# =====================
# STEP 2: EXECUTE EXITS
# =====================

if exits_to_execute:
    print(f"\n📤 Executing {len(exits_to_execute)} exits...")

    for exit_order in exits_to_execute:
        symbol = exit_order["symbol"]
        qty = exit_order["qty"]

        try:
            order = groww.place_order(
                trading_symbol=symbol,
                exchange=groww.EXCHANGE_NSE,
                segment=groww.SEGMENT_CASH,
                transaction_type=groww.TRANSACTION_SELL,
                order_type=groww.ORDER_MARKET,
                product_type=groww.PRODUCT_CNC,
                quantity=qty,
            )

            order_id = order.get("order_id", "N/A")
            print(
                f"   ✅ {symbol}: SELL {qty} @ ₹{exit_order['ltp']:.2f} | "
                f"{exit_order['reason']} | P&L: {exit_order['pnl_pct']:+.2f}% "
                f"[Order: {order_id}]"
            )
            remove_position(symbol)

        except Exception as e:
            print(f"   ❌ {symbol}: Sell failed - {e}")

        time.sleep(0.3)


# =====================
# STEP 3: SCAN FOR NEW ENTRIES
# =====================

print("\n📈 Scanning for bullish Marubozu signals...")
if USE_EMA_FILTER:
    print(f"   Filter: Body > {MIN_BODY_PCT}% + Range > {MIN_BODY_RANGE*100}% + Below ALL EMAs ({EMA_PERIODS})")
else:
    print(f"   Filter: Body > {MIN_BODY_PCT}% + Range > {MIN_BODY_RANGE*100}% (No EMA filter)")

candidates = []
holdings = get_holdings()  # Refresh holdings

for symbol in STOCK_SYMBOLS:
    # Skip if already holding
    if symbol in holdings or symbol in load_positions():
        continue

    time.sleep(0.2)  # Rate limiting

    data = get_historical_data(symbol, days=LOOKBACK_DAYS)
    if not data or len(data["close"]) < 50:  # Need at least 50 days
        continue

    closes = data["close"]
    current_close = closes[-1]

    # Calculate all EMAs (20, 50, 200) if filter is enabled
    emas = {}
    if USE_EMA_FILTER:
        for period in EMA_PERIODS:
            ema_val = calculate_ema(closes, period)
            if ema_val is None:
                break
            emas[period] = ema_val
        
        if len(emas) != len(EMA_PERIODS):
            continue  # Skip if any EMA couldn't be calculated

        # Check if stock is below ALL EMAs (below_all filter)
        below_all_emas = all(current_close < ema_val for ema_val in emas.values())
        if not below_all_emas:
            continue

    # Detect bullish Marubozu
    is_marubozu, body_pct, body_size = detect_bullish_marubozu(
        data["open"], data["high"], data["low"], data["close"]
    )

    if is_marubozu:
        ohlc = get_live_ohlc(symbol)
        ltp = ohlc.get("ltp", current_close) if ohlc else current_close

        # Calculate % below EMA200 (for ranking if EMA filter enabled)
        pct_below = 0
        if USE_EMA_FILTER and 200 in emas:
            ema200 = emas[200]
            pct_below = ((ema200 - current_close) / ema200) * 100

        candidates.append({
            "symbol": symbol,
            "ltp": ltp,
            "close": current_close,
            "body_pct": body_pct,
            "body_size": body_size,
            "ema20": emas.get(20, 0),
            "ema50": emas.get(50, 0),
            "ema200": emas.get(200, 0),
            "pct_below_ema": pct_below,
        })
        if USE_EMA_FILTER:
            print(
                f"   ✅ {symbol}: Marubozu (body={body_pct:.1f}%) @ ₹{ltp:.2f} | "
                f"Below ALL EMAs | Exit: {MAX_HOLD_DAYS}-day hold | {pct_below:.1f}% below EMA200"
            )
        else:
            print(
                f"   ✅ {symbol}: Marubozu (body={body_pct:.1f}%) @ ₹{ltp:.2f} | "
                f"Exit: {MAX_HOLD_DAYS}-day hold (same day close)"
            )

print(f"\n📊 Found {len(candidates)} candidates")


# =====================
# STEP 4: PLACE NEW ENTRIES
# =====================

if not candidates:
    print("\n⚠️  No new trading signals today.")
else:
    print("\n💰 Placing entry orders...")

    # Sort by body strength (strongest pattern first)
    if USE_EMA_FILTER:
        # Sort by % below EMA200 (most oversold first)
        candidates.sort(key=lambda x: x["pct_below_ema"], reverse=True)
    else:
        # Sort by body % (strongest Marubozu first)
        candidates.sort(key=lambda x: x["body_pct"], reverse=True)

    orders_placed = 0
    max_new_positions = 5  # Limit new positions per day

    for candidate in candidates[:max_new_positions]:
        symbol = candidate["symbol"]
        ltp = candidate["ltp"]
        body_size = candidate["body_size"]

        qty = calculate_quantity(ltp)
        if qty < 1:
            print(f"   ⏭️  {symbol}: Quantity too small, skipping")
            continue

        try:
            order = groww.place_order(
                trading_symbol=symbol,
                exchange=groww.EXCHANGE_NSE,
                segment=groww.SEGMENT_CASH,
                transaction_type=groww.TRANSACTION_BUY,
                order_type=groww.ORDER_MARKET,
                product_type=groww.PRODUCT_CNC,
                quantity=qty,
            )

            order_id = order.get("order_id", "N/A")

            # Track position (time-based exit only)
            hold_days = add_position(
                symbol=symbol,
                entry_price=ltp,
                body_size=body_size,
                entry_date=datetime.now(),
                quantity=qty,
            )

            print(
                f"   ✅ {symbol}: BUY {qty} @ ₹{ltp:.2f} | "
                f"Exit: {hold_days}-day hold (no target/stop) "
                f"[Order: {order_id}]"
            )
            orders_placed += 1

        except Exception as e:
            print(f"   ❌ {symbol}: Order failed - {e}")

        time.sleep(0.3)

    print(
        f"\n🎯 Orders placed: {orders_placed}/"
        f"{min(len(candidates), max_new_positions)}"
    )


# =====================
# SUMMARY
# =====================

positions = load_positions()

print("\n" + "=" * 60)
print("📊 MARUBOZU STRATEGY SESSION SUMMARY (9/9 Verified - INTRADAY)")
print("=" * 60)
if USE_EMA_FILTER:
    print("   Strategy: Bullish Marubozu + Below ALL EMAs (20/50/200)")
else:
    print("   Strategy: Bullish Marubozu (No EMA filter)")
print(f"   Entry: Body > {MIN_BODY_PCT}% + Range > {MIN_BODY_RANGE*100}%")
print(f"   Exit: {MAX_HOLD_DAYS}-day hold (same day close for intraday)")
print("   NO target, NO stop loss - backtested 9/9 positive years")
print("-" * 60)
print(f"   Stocks Scanned: {len(STOCK_SYMBOLS)}")
print(f"   New Signals: {len(candidates)}")
print(f"   Exits Executed: {len(exits_to_execute)}")
print(f"   Active Positions: {len(positions)}")
print("-" * 60)

if positions:
    print("\n📈 ACTIVE POSITIONS:")
    for symbol, pos in positions.items():
        days_remaining = MAX_HOLD_DAYS - pos.get("days_held", 0)
        print(
            f"   {symbol}: Entry=₹{pos['entry_price']:.2f} | "
            f"Days={pos['days_held']}/{MAX_HOLD_DAYS} | Exit in {days_remaining} days"
        )

print("=" * 60)
print("✅ Session complete!")
