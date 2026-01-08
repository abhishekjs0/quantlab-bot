"""
Bullish Marubozu Strategy - INTRADAY (MIS)

Groww Cloud Schedule:
    - Runs continuously 9:15 AM - 3:30 PM IST
    - Entry window: 9:15-9:30 AM
    - Exit window: 3:15-3:30 PM

Strategy:
    Entry: Bullish Marubozu on YESTERDAY (body >= 5% of price, >= 80% of range)
    Exit: Market close same day (time-based, no target/stop)
    Product: MIS (auto-squared off by exchange if not closed)

Backtest: 1,130 trades, +0.64%/trade, 52.7% WR, 9/9 years profitable

FIXES APPLIED:
    1. Historical candles timestamp format (string at index 0)
    2. Persistent storage in home directory
    3. detect_marubozu uses YESTERDAY's candle (second-to-last), not incomplete today
    4. Type hints and comprehensive error handling
    5. get_positions_for_user response field handling
    6. Proper float conversion for LTP and prices
    7. Rate limiting between API calls
"""

import json
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pyotp
from growwapi import GrowwAPI

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION (TOTP Flow - No daily expiry, expires 2055)
# ═══════════════════════════════════════════════════════════════════════════════

GROWW_TOTP_TOKEN = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTUxNjc3NDAsImlhdCI6MTc2Njc2Nzc0MCwibmJmIjoxNzY2NzY3NzQwLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJmYTVjOWUwZi02OGQ1LTRmYWItOTcwZi0zNjRiNTE3ZDk1ZDlcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiM2IzY2M4NTktYWYzNS00MWY3LWI0OTgtYmM2ODFlNDRjYzg3XCIsXCJkZXZpY2VJZFwiOlwiMTA1MDU5YzctNzFlOC01ZjNlLWI2MDctZGNjYzc4MGJjNWU4XCIsXCJzZXNzaW9uSWRcIjpcIjQ0ZTAzY2MwLWZlN2QtNDcxYy1iYjNlLTYwZDdiYzg3NDkyNVwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1seHBMN0FMeEhDTkRWT1YycnBuUzlSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIxNC4xMDIuMTYzLjExNiwxNzIuNzAuMjE4LjE4OCwzNS4yNDEuMjMuMTIzXCIsXCJ0d29GYUV4cGlyeVRzXCI6MjU1NTE2Nzc0MDIwMH0iLCJpc3MiOiJhcGV4LWF1dGgtcHJvZC1hcHAifQ.CVtkRiVV5KoFcDQiANb6TUIft8tufL8nBsmyNuth61cxPzXHEodcpCGs_AT0qLwk5Cabo1u-ki1SDJjBOV6_pA"
GROWW_TOTP_SECRET = "JVG42CV6PHCLMTVNSTKEQPN7AOAAL43F"

# Strategy params
INITIAL_CAPITAL = 100000
POSITION_SIZE_PCT = 0.05  # 5% per position = ₹5,000
MIN_BODY_PCT = 5.0  # Body must be >= 5% of open price
MIN_BODY_RANGE = 0.80  # Body must be >= 80% of total range
MAX_POSITIONS = 5

# Files - Use home directory for persistence across Groww Cloud restarts
HOME_DIR = os.path.expanduser("~")
POSITIONS_FILE = os.path.join(HOME_DIR, ".groww_marubozu_positions.json")
ENTRY_LOG_FILE = os.path.join(HOME_DIR, f".groww_marubozu_entries_{datetime.now().strftime('%Y-%m-%d')}.json")

# Stock universe
SYMBOLS = [
    "RELIANCE", "BHARTIARTL", "ICICIBANK", "SBIN", "BAJFINANCE", "LICI", "LT",
    "HCLTECH", "AXISBANK", "ULTRACEMCO", "TITAN", "BAJAJFINSV", "ADANIPORTS",
    "NTPC", "HAL", "BEL", "ADANIENT", "ASIANPAINT", "ADANIPOWER", "DMART",
    "COALINDIA", "IOC", "INDIGO", "TATASTEEL", "VEDL", "SBILIFE", "JIOFIN",
    "GRASIM", "LTIM", "HINDALCO", "DLF", "ADANIGREEN", "BPCL", "TECHM",
    "PIDILITIND", "IRFC", "TRENT", "BANKBARODA", "CHOLAFIN", "PNB",
    "TATAPOWER", "SIEMENS", "UNIONBANK", "PFC", "TATACONSUM", "BSE", "GAIL",
    "HDFCAMC", "ABB", "GMRAIRPORT", "MAZDOCK", "INDUSTOWER", "IDBI", "CGPOWER",
    "PERSISTENT", "HDFCBANK", "TCS", "INFY", "HINDUNILVR", "ITC", "MARUTI",
    "SUNPHARMA", "KOTAKBANK", "ONGC", "JSWSTEEL", "WIPRO", "POWERGRID",
    "NESTLEIND", "HINDZINC", "EICHERMOT", "TVSMOTOR", "DIVISLAB", "HDFCLIFE",
    "VBL", "SHRIRAMFIN", "MUTHOOTFIN", "BRITANNIA", "AMBUJACEM", "TORNTPHARM",
    "HEROMOTOCO", "CUMMINSIND", "CIPLA", "GODREJCP", "POLYCAB", "BOSCHLTD",
    "DRREDDY", "MAXHEALTH", "INDHOTEL", "APOLLOHOSP", "JINDALSTEL",
]

# ═══════════════════════════════════════════════════════════════════════════════
# INITIALIZE API (TOTP Flow)
# ═══════════════════════════════════════════════════════════════════════════════

print("🚀 Initializing Groww API (TOTP Flow)...")

if not GROWW_TOTP_TOKEN or not GROWW_TOTP_SECRET:
    print("❌ Missing GROWW_TOTP_TOKEN or GROWW_TOTP_SECRET")
    raise SystemExit(1)

try:
    totp = pyotp.TOTP(GROWW_TOTP_SECRET).now()
    token = GrowwAPI.get_access_token(api_key=GROWW_TOTP_TOKEN, totp=totp)
    groww = GrowwAPI(token)
    print("✅ API Ready")
except Exception as e:
    print(f"❌ Auth failed: {e}")
    raise SystemExit(1)

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════


def load_json(path: str, default: Any) -> Any:
    """Load JSON file or return default."""
    try:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    except Exception as e:
        print(f"   ⚠️ Error loading {path}: {e}")
    return default


def save_json(path: str, data: Any) -> bool:
    """Save data to JSON file. Returns True on success."""
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except Exception as e:
        print(f"   ⚠️ Error saving {path}: {e}")
        return False


def has_entered_today(symbol: str) -> bool:
    """Check if symbol was already entered today."""
    log = load_json(ENTRY_LOG_FILE, {"entries": []})
    return symbol in log.get("entries", [])


def log_entry(symbol: str) -> None:
    """Log that a symbol was entered today."""
    log = load_json(ENTRY_LOG_FILE, {"entries": []})
    if symbol not in log["entries"]:
        log["entries"].append(symbol)
        save_json(ENTRY_LOG_FILE, log)


def get_ltp(symbol: str) -> float:
    """Get last traded price. Returns 0 on failure."""
    try:
        resp = groww.get_ltp(
            segment=groww.SEGMENT_CASH,
            exchange_trading_symbols=f"NSE_{symbol}",
        )
        price = resp.get(f"NSE_{symbol}", 0)
        return float(price) if price else 0.0
    except Exception as e:
        print(f"   ⚠️ LTP error for {symbol}: {e}")
        return 0.0


def is_retryable_error(error_msg: str) -> bool:
    """Check if error is retryable based on Groww API docs."""
    error_lower = error_msg.lower()
    
    # Network/transient errors
    network_errors = ['timeout', 'connection', 'connect', 'max retries', 'temporarily unavailable']
    if any(x in error_lower for x in network_errors):
        return True
    
    # HTTP server errors
    if any(x in error_lower for x in ['502', '503', '504', '500']):
        return True
    
    # Check for actual error messages
    retryable_messages = ['internal error', 'unable to serve', 'service unavailable', 'try again']
    if any(x in error_lower for x in retryable_messages):
        return True
    
    # Default: retry unknown errors
    return True


def get_daily_candles(symbol: str, days: int = 10, max_retries: int = 3) -> List[Dict]:
    """
    Get historical daily candles with retry logic.
    
    Groww candle format: [timestamp_str, open, high, low, close, volume, oi]
    where timestamp_str is "YYYY-MM-DDTHH:mm:ss" format
    
    Returns list of dicts with keys: timestamp, open, high, low, close
    """
    end = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = groww.get_historical_candles(
                exchange=groww.EXCHANGE_NSE,
                segment=groww.SEGMENT_CASH,
                groww_symbol=f"NSE-{symbol}",
                start_time=start,
                end_time=end,
                candle_interval=groww.CANDLE_INTERVAL_DAY,
            )
            
            raw_candles = resp.get("candles", []) if resp else []
            
            candles = []
            for c in raw_candles:
                if not c or len(c) < 5:
                    continue
                
                try:
                    # c[0] = timestamp string, c[1] = open, c[2] = high, c[3] = low, c[4] = close
                    candles.append({
                        "timestamp": c[0],
                        "open": float(c[1]),
                        "high": float(c[2]),
                        "low": float(c[3]),
                        "close": float(c[4]),
                    })
                except (ValueError, TypeError, IndexError):
                    continue
            
            return candles
        
        except Exception as e:
            last_error = e
            if is_retryable_error(str(e)) and attempt < max_retries:
                wait_time = attempt * 2
                print(f"   ⚠️ Candles error for {symbol} (attempt {attempt}/{max_retries}): {e}")
                print(f"      Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                break
    
    print(f"   ⚠️ Candles error for {symbol}: {last_error}")
    return []


def detect_marubozu(candles: List[Dict]) -> Tuple[bool, float]:
    """
    Check if YESTERDAY's candle is a bullish Marubozu.
    
    CRITICAL: At 9:15 AM, the last candle in the list is TODAY's incomplete candle.
    We need to check the SECOND-TO-LAST candle (yesterday's completed candle).
    
    Returns (is_marubozu, body_pct).
    """
    if len(candles) < 2:
        return False, 0.0
    
    # Use second-to-last candle = yesterday's completed daily candle
    yesterday = candles[-2]
    
    o = yesterday["open"]
    h = yesterday["high"]
    low = yesterday["low"]
    close = yesterday["close"]
    
    # Must be bullish (close > open)
    body = close - o
    if body <= 0:
        return False, 0.0
    
    # Calculate range
    total_range = h - low
    if total_range <= 0:
        return False, 0.0
    
    # Body must be >= MIN_BODY_PCT of open price
    body_pct = (body / o) * 100
    
    # Body must be >= MIN_BODY_RANGE of total range
    body_ratio = body / total_range
    
    if body_pct >= MIN_BODY_PCT and body_ratio >= MIN_BODY_RANGE:
        return True, body_pct
    
    return False, 0.0


def get_mis_positions() -> Dict[str, Dict]:
    """
    Get current MIS positions.
    
    Returns dict of {symbol: {"qty": int, "avg": float}}
    """
    try:
        resp = groww.get_positions_for_user(segment=groww.SEGMENT_CASH)
        positions = {}
        
        for p in resp.get("positions", []):
            sym = p.get("trading_symbol")
            qty = p.get("quantity", 0)
            product = p.get("product", "")
            
            # Only include MIS positions with positive quantity
            if sym and qty and product == "MIS":
                try:
                    qty = int(float(qty))
                except (ValueError, TypeError):
                    continue
                
                if qty > 0:
                    # Try multiple possible field names for average price
                    avg = (
                        p.get("average_price") or 
                        p.get("net_price") or 
                        p.get("buy_average") or
                        p.get("credit_price") or 
                        0
                    )
                    try:
                        avg = float(avg) if avg else 0.0
                    except (ValueError, TypeError):
                        avg = 0.0
                    
                    positions[sym] = {"qty": qty, "avg": avg}
        
        return positions
        
    except Exception as e:
        print(f"   ⚠️ Positions error: {e}")
        return {}


def place_order(symbol: str, qty: int, txn_type: str) -> Dict:
    """
    Place MIS order.
    
    Args:
        symbol: Trading symbol
        qty: Quantity
        txn_type: groww.TRANSACTION_TYPE_BUY or _SELL
    
    Returns order response dict.
    """
    return groww.place_order(
        trading_symbol=symbol,
        exchange=groww.EXCHANGE_NSE,
        segment=groww.SEGMENT_CASH,
        transaction_type=txn_type,
        order_type=groww.ORDER_TYPE_MARKET,
        product=groww.PRODUCT_MIS,
        quantity=qty,
        validity=groww.VALIDITY_DAY,
    )


def calc_qty(price: float) -> int:
    """Calculate quantity based on position size."""
    if price <= 0:
        return 0
    return max(1, int((INITIAL_CAPITAL * POSITION_SIZE_PCT) / price))


# ═══════════════════════════════════════════════════════════════════════════════
# TIME CHECK
# ═══════════════════════════════════════════════════════════════════════════════

now = datetime.now()
h, m = now.hour, now.minute

is_entry = h == 9 and 15 <= m <= 30
is_exit = h == 15 and 15 <= m <= 30
is_market = (h == 9 and m >= 15) or (10 <= h <= 14) or (h == 15 and m <= 30)

print(f"\n⏰ {now.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"   Entry Window: {is_entry} | Exit Window: {is_exit} | Market: {is_market}")

if not is_market:
    print("⛔ Outside market hours")
    raise SystemExit(0)

# ═══════════════════════════════════════════════════════════════════════════════
# EXIT LOGIC (3:15-3:30 PM)
# ═══════════════════════════════════════════════════════════════════════════════

if is_exit:
    print("\n📤 EXIT WINDOW - Closing all MIS positions...")
    positions = get_mis_positions()
    tracked = load_json(POSITIONS_FILE, {})
    
    if not positions:
        print("   No MIS positions to close")
    else:
        exits = 0
        total_pnl = 0.0
        
        for sym, pos in positions.items():
            try:
                ltp = get_ltp(sym)
                entry = tracked.get(sym, {}).get("entry", pos["avg"])
                pnl = ((ltp - entry) / entry * 100) if entry > 0 and ltp > 0 else 0
                
                order = place_order(sym, pos["qty"], groww.TRANSACTION_TYPE_SELL)
                oid = order.get("groww_order_id", "N/A")
                status = order.get("order_status", "UNKNOWN")
                
                print(f"   ✅ {sym}: SELL {pos['qty']} @ ₹{ltp:.2f} | P&L: {pnl:+.2f}% [{oid}:{status}]")
                exits += 1
                total_pnl += pnl
            except Exception as e:
                print(f"   ❌ {sym}: {e}")
            time.sleep(0.3)
        
        avg_pnl = total_pnl / exits if exits > 0 else 0
        print(f"\n   Closed: {exits} positions | Average P&L: {avg_pnl:+.2f}%")
    
    # Clear tracked positions
    save_json(POSITIONS_FILE, {})
    print("✅ All MIS positions closed")
    raise SystemExit(0)

# ═══════════════════════════════════════════════════════════════════════════════
# MONITORING (Between Entry and Exit windows)
# ═══════════════════════════════════════════════════════════════════════════════

if not is_entry and not is_exit:
    print("\n⏸️ Monitoring mode (between entry and exit windows)")
    
    positions = get_mis_positions()
    tracked = load_json(POSITIONS_FILE, {})
    
    if positions:
        print(f"   Active MIS positions: {len(positions)}")
        total_pnl = 0.0
        
        for sym, pos in positions.items():
            ltp = get_ltp(sym)
            entry = tracked.get(sym, {}).get("entry", pos["avg"])
            pnl = ((ltp - entry) / entry * 100) if entry > 0 and ltp > 0 else 0
            total_pnl += pnl
            print(f"   📊 {sym}: ₹{entry:.2f} → ₹{ltp:.2f} ({pnl:+.2f}%)")
            time.sleep(0.05)
        
        avg_pnl = total_pnl / len(positions)
        print(f"\n   Average P&L: {avg_pnl:+.2f}%")
        print("   Exit at 3:15 PM")
    else:
        print("   No active positions")
    
    raise SystemExit(0)

# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY LOGIC (9:15-9:30 AM)
# ═══════════════════════════════════════════════════════════════════════════════

print(f"\n📈 ENTRY WINDOW - Scanning {len(SYMBOLS)} stocks for Marubozu patterns...")
print("   Looking for bullish Marubozu on YESTERDAY's candle")

candidates = []
scanned = 0

for sym in SYMBOLS:
    time.sleep(0.12)  # Rate limiting
    scanned += 1
    
    if scanned % 20 == 0:
        print(f"   Scanned {scanned}/{len(SYMBOLS)}...")
    
    candles = get_daily_candles(sym)
    
    if len(candles) < 2:
        continue
    
    is_maru, body_pct = detect_marubozu(candles)
    
    if is_maru:
        ltp = get_ltp(sym)
        if ltp > 0:
            candidates.append({"sym": sym, "ltp": ltp, "body": body_pct})
            yesterday = candles[-2]
            print(f"   ✅ {sym}: Marubozu! Body={body_pct:.1f}% | Yesterday: O={yesterday['open']:.2f} C={yesterday['close']:.2f} | LTP=₹{ltp:.2f}")

print(f"\n📊 Found {len(candidates)} Marubozu signals")

if not candidates:
    print("⚠️ No Marubozu signals today")
    raise SystemExit(0)

# Sort by body strength (strongest first)
candidates.sort(key=lambda x: x["body"], reverse=True)

# Check existing positions
existing = get_mis_positions()
available_slots = MAX_POSITIONS - len(existing)

print(f"\n💰 Placing MIS orders (Available slots: {available_slots}/{MAX_POSITIONS})...")

if available_slots <= 0:
    print("   ⚠️ Max positions reached")
    raise SystemExit(0)

tracked = load_json(POSITIONS_FILE, {})
placed = 0

for c in candidates[:available_slots]:
    sym, ltp, body = c["sym"], c["ltp"], c["body"]

    if has_entered_today(sym):
        print(f"   ⏭️ {sym}: Already entered today")
        continue
    
    if sym in existing:
        print(f"   ⏭️ {sym}: Already have position")
        continue

    qty = calc_qty(ltp)
    if qty < 1:
        print(f"   ⏭️ {sym}: Qty too low at ₹{ltp:.2f}")
        continue

    try:
        order = place_order(sym, qty, groww.TRANSACTION_TYPE_BUY)
        oid = order.get("groww_order_id", "N/A")
        status = order.get("order_status", "UNKNOWN")
        
        tracked[sym] = {
            "entry": ltp,
            "qty": qty,
            "body": body,
            "entry_time": datetime.now().isoformat(),
        }
        log_entry(sym)
        
        print(f"   ✅ {sym}: BUY {qty} @ ₹{ltp:.2f} | Body: {body:.1f}% | Value: ₹{qty*ltp:,.0f} [{oid}:{status}]")
        placed += 1
    except Exception as e:
        print(f"   ❌ {sym}: {e}")
    
    time.sleep(0.3)

save_json(POSITIONS_FILE, tracked)
print(f"\n🎯 Placed: {placed}/{min(len(candidates), available_slots)}")

# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("📊 MARUBOZU INTRADAY SUMMARY")
print("=" * 60)
print(f"   Signals Found: {len(candidates)}")
print(f"   Orders Placed: {placed}")
print(f"   Active Positions: {len(tracked)}/{MAX_POSITIONS}")
print(f"   Exit: 3:15 PM (time-based)")
print("=" * 60)

if tracked:
    print("\n📁 TODAY'S ENTRIES:")
    for sym, pos in tracked.items():
        print(f"   {sym}: {pos['qty']} @ ₹{pos['entry']:.2f} | Body: {pos['body']:.1f}%")

print("\n✅ Strategy execution complete")
