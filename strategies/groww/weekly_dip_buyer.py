"""
Weekly Dip Buyer Strategy - CNC (Delivery)

Groww Cloud Schedule:
    - Runs continuously 9:15 AM - 3:30 PM IST
    - Daily: Check 8% stop loss
    - Monday 9:15-9:30 AM: Check continuations + new entries

Strategy (Mean Reversion):
    Entry (Monday): Bottom 20% weekly performers + >5% drop + NIFTY down
    Hold: Continue if still qualifies next Monday
    Exit: No longer qualifies OR 8% stop loss
    Product: CNC (delivery, held in DEMAT)

Backtest: 700 trades, +35.16% total, +1.06%/trade, 51.1% WR, 10/11 years

FIXES APPLIED:
    1. Historical candles timestamp format (string, not index shift)
    2. Persistent storage in home directory
    3. Holdings response field handling with error checks
    4. Removed duplicate API init
    5. Type hints and comprehensive error handling
    6. get_ltp returns float with validation
    7. Proper weekly return candle indexing
    8. Variable scope fixes
"""

import json
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pyotp
from growwapi import GrowwAPI

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION (TOTP Flow - No daily expiry, expires 2055)
# ═══════════════════════════════════════════════════════════════════════════════

GROWW_TOTP_TOKEN = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTUxNjc3NDAsImlhdCI6MTc2Njc2Nzc0MCwibmJmIjoxNzY2NzY3NzQwLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJmYTVjOWUwZi02OGQ1LTRmYWItOTcwZi0zNjRiNTE3ZDk1ZDlcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiM2IzY2M4NTktYWYzNS00MWY3LWI0OTgtYmM2ODFlNDRjYzg3XCIsXCJkZXZpY2VJZFwiOlwiMTA1MDU5YzctNzFlOC01ZjNlLWI2MDctZGNjYzc4MGJjNWU4XCIsXCJzZXNzaW9uSWRcIjpcIjQ0ZTAzY2MwLWZlN2QtNDcxYy1iYjNlLTYwZDdiYzg3NDkyNVwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1seHBMN0FMeEhDTkRWT1YycnBuUzlSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIxNC4xMDIuMTYzLjExNiwxNzIuNzAuMjE4LjE4OCwzNS4yNDEuMjMuMTIzXCIsXCJ0d29GYUV4cGlyeVRzXCI6MjU1NTE2Nzc0MDIwMH0iLCJpc3MiOiJhcGV4LWF1dGgtcHJvZC1hcHAifQ.CVtkRiVV5KoFcDQiANb6TUIft8tufL8nBsmyNuth61cxPzXHEodcpCGs_AT0qLwk5Cabo1u-ki1SDJjBOV6_pA"
GROWW_TOTP_SECRET = "JVG42CV6PHCLMTVNSTKEQPN7AOAAL43F"

# Strategy params
INITIAL_CAPITAL = 100000
POSITION_SIZE_PCT = 0.10  # 10% per position
MIN_DROP_PCT = 5.0  # Minimum 5% weekly drop
SELECT_BOTTOM_PCT = 20.0  # Bottom 20% performers
STOP_PCT = 0.08  # 8% stop loss
MAX_POSITIONS = 5

# Files - Use home directory for persistence across Groww Cloud restarts
# Fallback to /tmp if HOME is not set (Groww Cloud environment)
HOME_DIR = os.path.expanduser("~")
if HOME_DIR == "/" or not HOME_DIR:
    HOME_DIR = "/tmp"
POSITIONS_FILE = os.path.join(HOME_DIR, ".groww_weekly_dip_positions.json")
ENTRY_LOG_FILE = os.path.join(HOME_DIR, f".groww_weekly_dip_entries_{datetime.now().strftime('%Y-W%V')}.json")

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
# INITIALIZE API (TOTP Flow with Retry)
# ═══════════════════════════════════════════════════════════════════════════════

# Groww API error codes (from https://groww.in/trade-api/docs/curl)
RETRYABLE_ERRORS = {
    'GA000': 'Internal error occurred',
    'GA003': 'Unable to serve request currently',
}
NON_RETRYABLE_ERRORS = {
    'GA001': 'Bad request',
    'GA005': 'User not authorised',
    'GA006': 'Cannot process this request',
}


def is_retryable_error(error_msg: str) -> bool:
    """Check if error is retryable based on Groww API docs."""
    error_lower = error_msg.lower()
    
    # Network/connection errors - always retry
    network_errors = ['timeout', 'connection', 'connect', 'max retries', 'temporarily unavailable']
    if any(x in error_lower for x in network_errors):
        return True
    
    # HTTP 5xx errors - retry
    if any(x in error_lower for x in ['502', '503', '504', '500']):
        return True
    
    # Groww API retryable error codes
    if any(code in error_msg for code in RETRYABLE_ERRORS):
        return True
    
    # Non-retryable Groww API errors
    if any(code in error_msg for code in NON_RETRYABLE_ERRORS):
        return False
    
    return False


def init_groww_api(max_retries: int = 3, retry_delay: int = 5) -> GrowwAPI:
    """Initialize Groww API with retry logic for transient failures."""
    print("🚀 Initializing Groww API (TOTP Flow)...")
    
    if not GROWW_TOTP_TOKEN or not GROWW_TOTP_SECRET:
        print("❌ Missing GROWW_TOTP_TOKEN or GROWW_TOTP_SECRET")
        raise SystemExit(1)
    
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            totp = pyotp.TOTP(GROWW_TOTP_SECRET).now()
            token = GrowwAPI.get_access_token(api_key=GROWW_TOTP_TOKEN, totp=totp)
            api = GrowwAPI(token)
            print("✅ API Ready")
            return api
        except Exception as e:
            last_error = e
            error_msg = str(e)
            
            if is_retryable_error(error_msg) and attempt < max_retries:
                wait_time = retry_delay * attempt  # Exponential backoff
                print(f"⚠️ Auth attempt {attempt}/{max_retries} failed: {e}")
                print(f"   Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                break
    
    print(f"❌ Auth failed after {max_retries} attempts: {last_error}")
    raise SystemExit(1)


groww = init_groww_api()

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


def has_entered_this_week(symbol: str) -> bool:
    """Check if symbol was already entered this week."""
    log = load_json(ENTRY_LOG_FILE, {"entries": []})
    return symbol in log.get("entries", [])


def log_entry(symbol: str) -> None:
    """Log that a symbol was entered this week."""
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


def get_ohlc(symbol: str) -> Dict[str, float]:
    """
    Get today's OHLC. Returns empty dict on failure.
    
    Python SDK returns OHLC as a proper dict:
    {"open": 22516.45, "high": 22613.3, "low": 22526.4, "close": 22547.55}
    
    But cURL returns string format - handle both for safety.
    """
    try:
        resp = groww.get_ohlc(
            segment=groww.SEGMENT_CASH,
            exchange_trading_symbols=f"NSE_{symbol}",
        )
        ohlc_raw = resp.get(f"NSE_{symbol}", {})
        
        # Python SDK returns proper dict
        if isinstance(ohlc_raw, dict):
            return {
                "open": float(ohlc_raw.get("open", 0) or 0),
                "high": float(ohlc_raw.get("high", 0) or 0),
                "low": float(ohlc_raw.get("low", 0) or 0),
                "close": float(ohlc_raw.get("close", 0) or 0),
            }
        
        # Fallback: Parse string format (cURL raw response)
        if isinstance(ohlc_raw, str) and ohlc_raw:
            import re
            result = {}
            for key in ["open", "high", "low", "close"]:
                match = re.search(rf"{key}:\s*([\d.]+)", ohlc_raw)
                result[key] = float(match.group(1)) if match else 0.0
            return result
        
        return {}
    except Exception as e:
        print(f"   ⚠️ OHLC error for {symbol}: {e}")
        return {}


def get_weekly_return(symbol: str) -> Optional[float]:
    """
    Get last completed week's return.
    
    Groww candle format: [timestamp_str, open, high, low, close, volume, oi]
    where timestamp_str is "YYYY-MM-DDTHH:mm:ss" format
    
    Returns percentage return or None on failure.
    """
    try:
        end = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        start = (datetime.now() - timedelta(days=21)).strftime("%Y-%m-%d %H:%M:%S")
        
        resp = groww.get_historical_candles(
            exchange=groww.EXCHANGE_NSE,
            segment=groww.SEGMENT_CASH,
            groww_symbol=f"NSE-{symbol}",
            start_time=start,
            end_time=end,
            candle_interval=groww.CANDLE_INTERVAL_WEEK,
        )
        
        candles = resp.get("candles", []) if resp else []
        
        # Validate candles - format: [timestamp, open, high, low, close, volume, oi]
        valid = []
        for c in candles:
            if c and len(c) >= 5:
                try:
                    # c[0] is timestamp string, c[1] is open, c[4] is close
                    open_price = float(c[1])
                    close_price = float(c[4])
                    if open_price > 0 and close_price > 0:
                        valid.append({"open": open_price, "close": close_price})
                except (ValueError, TypeError, IndexError):
                    continue
        
        if len(valid) < 2:
            return None
        
        # On Monday before market close, last candle is current incomplete week
        # Use second-to-last for last completed week
        # On other days, also use second-to-last
        last_complete = valid[-2]  # Always use second-to-last for completed week
        
        return ((last_complete["close"] - last_complete["open"]) / last_complete["open"]) * 100
        
    except Exception as e:
        print(f"   ⚠️ Weekly return error for {symbol}: {e}")
        return None


def get_holdings() -> Dict[str, Dict]:
    """
    Get CNC holdings.
    
    Returns dict of {symbol: {"qty": int, "avg": float}}
    """
    try:
        resp = groww.get_holdings_for_user()
        holdings = {}
        
        for h in resp.get("holdings", []):
            symbol = h.get("trading_symbol")
            qty = h.get("quantity", 0)
            avg = h.get("average_price", 0)
            
            # Handle both int and float quantities
            try:
                qty = int(float(qty)) if qty else 0
                avg = float(avg) if avg else 0.0
            except (ValueError, TypeError):
                continue
            
            if symbol and qty > 0:
                holdings[symbol] = {"qty": qty, "avg": avg}
        
        return holdings
        
    except Exception as e:
        print(f"   ⚠️ Holdings error: {e}")
        return {}


def place_order(symbol: str, qty: int, txn_type: str) -> Dict:
    """
    Place CNC order.
    
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
        product=groww.PRODUCT_CNC,
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
is_monday = now.weekday() == 0
is_entry = h == 9 and 15 <= m <= 30
is_market = (h == 9 and m >= 15) or (10 <= h <= 14) or (h == 15 and m <= 30)

print(f"\n📅 {now.strftime('%A %Y-%m-%d %H:%M:%S')}")
print(f"   Monday: {is_monday} | Entry Window: {is_entry} | Market: {is_market}")

if not is_market:
    print("⛔ Outside market hours")
    raise SystemExit(0)

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1: CHECK STOP LOSSES (DAILY)
# ═══════════════════════════════════════════════════════════════════════════════

print("\n📊 Checking stop losses...")

positions = load_json(POSITIONS_FILE, {})
holdings = get_holdings()
stops = []
positions_to_remove = []

for sym, pos in list(positions.items()):
    if sym not in holdings:
        print(f"   ⚠️ {sym}: Not in holdings, removing from tracking")
        positions_to_remove.append(sym)
        continue

    ohlc = get_ohlc(sym)
    ltp = get_ltp(sym) or ohlc.get("close", 0)
    low = ohlc.get("low", ltp) or ltp
    entry = pos.get("entry", 0)
    stop = pos.get("stop", 0)
    pnl = ((ltp - entry) / entry * 100) if entry > 0 else 0

    if low > 0 and stop > 0 and low <= stop:
        stops.append({"sym": sym, "qty": holdings[sym]["qty"], "ltp": ltp, "pnl": pnl})
        print(f"   🛑 {sym}: STOP HIT (low={low:.2f} <= stop={stop:.2f})")
    else:
        dist = ((ltp - stop) / ltp * 100) if ltp > 0 and stop > 0 else 0
        print(f"   📊 {sym}: ₹{ltp:.2f} | P&L={pnl:+.2f}% | Stop={stop:.2f} ({dist:.1f}% away)")

# Remove stale positions
for sym in positions_to_remove:
    if sym in positions:
        del positions[sym]

save_json(POSITIONS_FILE, positions)

# Execute stops
for s in stops:
    try:
        order = place_order(s["sym"], s["qty"], groww.TRANSACTION_TYPE_SELL)
        oid = order.get("groww_order_id", "N/A")
        print(f"   ✅ {s['sym']}: SELL {s['qty']} @ ₹{s['ltp']:.2f} | P&L: {s['pnl']:+.2f}% [{oid}]")
        if s["sym"] in positions:
            del positions[s["sym"]]
    except Exception as e:
        print(f"   ❌ {s['sym']}: {e}")
    time.sleep(0.3)

save_json(POSITIONS_FILE, positions)

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2: MONDAY LOGIC
# ═══════════════════════════════════════════════════════════════════════════════

if not is_monday:
    print(f"\n⏸️ {now.strftime('%A')} - Stop loss check only")
    print(f"   Active positions: {len(positions)}")
    raise SystemExit(0)

if not is_entry:
    print("\n⏸️ Monday outside entry window (9:15-9:30 AM)")
    print(f"   Active positions: {len(positions)}")
    raise SystemExit(0)

print("\n📈 Monday Entry Window - Full scan...")

# Check NIFTY using NIFTYBEES ETF
print("\n📊 Checking NIFTY...")
nifty_ret = get_weekly_return("NIFTYBEES")

if nifty_ret is not None:
    nifty_down = nifty_ret < 0
    print(f"   NIFTY: {nifty_ret:+.2f}% ({'DOWN ✅' if nifty_down else 'UP ⛔'})")
else:
    # If NIFTY data unavailable, try direct index
    print("   ⚠️ NIFTYBEES data unavailable, trying NIFTY50 index...")
    nifty_ret = get_weekly_return("NIFTY 50")
    if nifty_ret is not None:
        nifty_down = nifty_ret < 0
        print(f"   NIFTY: {nifty_ret:+.2f}% ({'DOWN ✅' if nifty_down else 'UP ⛔'})")
    else:
        # Fallback: proceed with caution
        print("   ⚠️ Could not get NIFTY return - proceeding without NIFTY filter")
        nifty_down = True

if not nifty_down:
    print("\n⛔ NIFTY up - Exiting all positions (strategy requires NIFTY down)")
    holdings = get_holdings()  # Refresh
    
    for sym, pos in list(positions.items()):
        if sym not in holdings:
            continue
        try:
            ltp = get_ltp(sym)
            pnl = ((ltp - pos.get("entry", 0)) / pos.get("entry", 1) * 100) if pos.get("entry") else 0
            order = place_order(sym, holdings[sym]["qty"], groww.TRANSACTION_TYPE_SELL)
            oid = order.get("groww_order_id", "N/A")
            print(f"   ✅ {sym}: SELL | P&L: {pnl:+.2f}% [{oid}]")
            del positions[sym]
        except Exception as e:
            print(f"   ❌ {sym}: {e}")
        time.sleep(0.3)
    
    save_json(POSITIONS_FILE, positions)
    raise SystemExit(0)

# Get all weekly returns
print("\n📊 Fetching weekly returns...")
returns = []
scanned = 0

for sym in SYMBOLS:
    time.sleep(0.12)  # Rate limiting
    scanned += 1
    
    if scanned % 20 == 0:
        print(f"   Scanned {scanned}/{len(SYMBOLS)}...")
    
    ret = get_weekly_return(sym)
    if ret is not None:
        returns.append({"sym": sym, "ret": ret})

if not returns:
    print("⚠️ No return data available")
    raise SystemExit(0)

# Sort by return (worst first)
returns.sort(key=lambda x: x["ret"])
n_bottom = max(1, int(len(returns) * SELECT_BOTTOM_PCT / 100))
bottom_set = {r["sym"] for r in returns[:n_bottom]}

print(f"\n   Total stocks with data: {len(returns)}")
print(f"   Bottom {SELECT_BOTTOM_PCT:.0f}%: {n_bottom} stocks")
print(f"   Worst: {returns[0]['sym']} ({returns[0]['ret']:+.2f}%)")
print(f"   Best:  {returns[-1]['sym']} ({returns[-1]['ret']:+.2f}%)")

# Check continuations
print("\n📊 Checking existing positions for continuation...")
exits = []
holdings = get_holdings()  # Refresh

for sym, pos in list(positions.items()):
    if sym not in holdings:
        continue
    
    # Find this symbol's return
    sym_ret = next((r["ret"] for r in returns if r["sym"] == sym), None)
    
    # Still qualifies: in bottom set AND dropped > MIN_DROP_PCT
    qualifies = sym in bottom_set and sym_ret is not None and sym_ret <= -MIN_DROP_PCT

    if qualifies:
        pos["weeks"] = pos.get("weeks", 1) + 1
        print(f"   ✅ {sym}: Still qualifies ({sym_ret:+.2f}%) - Week #{pos['weeks']}")
    else:
        reason = "not in bottom" if sym not in bottom_set else f"drop {sym_ret:.2f}% < {MIN_DROP_PCT}%"
        exits.append({"sym": sym, "qty": holdings[sym]["qty"], "entry": pos.get("entry", 0), "reason": reason})
        print(f"   📤 {sym}: No longer qualifies ({reason})")

# Execute exits
for e in exits:
    try:
        ltp = get_ltp(e["sym"])
        pnl = ((ltp - e["entry"]) / e["entry"] * 100) if e["entry"] > 0 else 0
        order = place_order(e["sym"], e["qty"], groww.TRANSACTION_TYPE_SELL)
        oid = order.get("groww_order_id", "N/A")
        print(f"   ✅ {e['sym']}: SELL {e['qty']} | P&L: {pnl:+.2f}% | {e['reason']} [{oid}]")
        if e["sym"] in positions:
            del positions[e["sym"]]
    except Exception as ex:
        print(f"   ❌ {e['sym']}: {ex}")
    time.sleep(0.3)

save_json(POSITIONS_FILE, positions)

# New entries
print("\n📈 Scanning for new entries...")

# Candidates: bottom performers with minimum drop
candidates = [r for r in returns[:n_bottom] if r["ret"] <= -MIN_DROP_PCT]

# Filter out already held
holdings = get_holdings()  # Refresh
candidates = [c for c in candidates if c["sym"] not in holdings]

print(f"   Candidates meeting criteria: {len(candidates)}")

if candidates:
    for c in candidates[:10]:  # Show top 10
        print(f"   🎯 {c['sym']}: {c['ret']:+.2f}%")

# Calculate available slots
current_positions = len([s for s in positions if s in holdings])
available_slots = MAX_POSITIONS - current_positions

print(f"\n💰 Placing CNC orders (Available slots: {available_slots}/{MAX_POSITIONS})...")

if available_slots <= 0:
    print("   ⚠️ Max positions reached")
else:
    placed = 0
    
    for c in candidates[:available_slots]:
        sym = c["sym"]
        
        if has_entered_this_week(sym):
            print(f"   ⏭️ {sym}: Already entered this week")
            continue
        
        if sym in positions:
            print(f"   ⏭️ {sym}: Already tracking")
            continue
        
        ltp = get_ltp(sym)
        if ltp <= 0:
            print(f"   ⏭️ {sym}: Invalid LTP")
            continue
        
        qty = calc_qty(ltp)
        if qty < 1:
            print(f"   ⏭️ {sym}: Qty too low at ₹{ltp:.2f}")
            continue
        
        stop = ltp * (1 - STOP_PCT)
        
        try:
            order = place_order(sym, qty, groww.TRANSACTION_TYPE_BUY)
            oid = order.get("groww_order_id", "N/A")
            status = order.get("order_status", "UNKNOWN")
            
            positions[sym] = {
                "entry": ltp,
                "stop": stop,
                "qty": qty,
                "weeks": 1,
                "drop": c["ret"],
                "entry_date": datetime.now().isoformat(),
            }
            log_entry(sym)
            
            print(f"   ✅ {sym}: BUY {qty} @ ₹{ltp:.2f} | Stop: ₹{stop:.2f} | Drop: {c['ret']:+.2f}% [{oid}:{status}]")
            placed += 1
        except Exception as e:
            print(f"   ❌ {sym}: {e}")
        
        time.sleep(0.3)
    
    save_json(POSITIONS_FILE, positions)
    print(f"\n🎯 Placed: {placed}")

# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("📊 WEEKLY DIP BUYER SUMMARY")
print("=" * 60)
print(f"   NIFTY: {nifty_ret:+.2f}%" if nifty_ret else "   NIFTY: N/A")
print(f"   Stops Executed: {len(stops)}")
print(f"   Exits (no qualify): {len(exits)}")
print(f"   Active Positions: {len(positions)}/{MAX_POSITIONS}")
print("=" * 60)

if positions:
    print("\n📁 CURRENT POSITIONS:")
    holdings = get_holdings()
    
    for sym, pos in positions.items():
        if sym not in holdings:
            continue
        ltp = get_ltp(sym)
        entry = pos.get("entry", 0)
        pnl = ((ltp - entry) / entry * 100) if entry > 0 and ltp > 0 else 0
        weeks = pos.get("weeks", 1)
        print(f"   {sym}: Week #{weeks} | ₹{entry:.2f} → ₹{ltp:.2f} ({pnl:+.2f}%)")
        time.sleep(0.05)

print("\n✅ Strategy execution complete")
