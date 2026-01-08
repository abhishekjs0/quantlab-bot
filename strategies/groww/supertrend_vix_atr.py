"""
Supertrend VIX+ATR% Strategy - CNC (Delivery)

Groww Cloud Schedule:
    - Runs daily 9:15-9:30 AM IST (after market open)
    - Entry: When Supertrend flips to uptrend + filters pass (on next day open)
    - Exit: When Supertrend flips to downtrend (on next day open)
    - Product: CNC (delivery, held in DEMAT)

Strategy:
    - Supertrend(3.0, 12) for trend direction
    - VIX Filter: VIX < 13 OR VIX > 19 (avoid neutral zone)
    - ATR% Filter: ATR% > 3 (require minimum volatility)
    - No stop loss (exit only on trend flip)

Stock Universe: 299 stocks filtered for win rate >= 40% in backtests

Backtest Results (MAX period):
    - Net P&L: 3,105.84%
    - CAGR: 40.87%
    - Win Rate: 42.84%
    - Trades: 7,692

Position Sizing: 5% of 1,00,000 = ₹5,000 per position
"""

import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import numpy as np
import pyotp
from growwapi import GrowwAPI

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION (TOTP Flow - No daily expiry, expires 2055)
# ═══════════════════════════════════════════════════════════════════════════════

GROWW_TOTP_TOKEN = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTUxNjc3NDAsImlhdCI6MTc2Njc2Nzc0MCwibmJmIjoxNzY2NzY3NzQwLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJmYTVjOWUwZi02OGQ1LTRmYWItOTcwZi0zNjRiNTE3ZDk1ZDlcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiM2IzY2M4NTktYWYzNS00MWY3LWI0OTgtYmM2ODFlNDRjYzg3XCIsXCJkZXZpY2VJZFwiOlwiMTA1MDU5YzctNzFlOC01ZjNlLWI2MDctZGNjYzc4MGJjNWU4XCIsXCJzZXNzaW9uSWRcIjpcIjQ0ZTAzY2MwLWZlN2QtNDcxYy1iYjNlLTYwZDdiYzg3NDkyNVwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1seHBMN0FMeEhDTkRWT1YycnBuUzlSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIxNC4xMDIuMTYzLjExNiwxNzIuNzAuMjE4LjE4OCwzNS4yNDEuMjMuMTIzXCIsXCJ0d29GYUV4cGlyeVRzXCI6MjU1NTE2Nzc0MDIwMH0iLCJpc3MiOiJhcGV4LWF1dGgtcHJvZC1hcHAifQ.CVtkRiVV5KoFcDQiANb6TUIft8tufL8nBsmyNuth61cxPzXHEodcpCGs_AT0qLwk5Cabo1u-ki1SDJjBOV6_pA"
GROWW_TOTP_SECRET = "JVG42CV6PHCLMTVNSTKEQPN7AOAAL43F"

# ═══════════════════════════════════════════════════════════════════════════════
# STRATEGY PARAMETERS
# ═══════════════════════════════════════════════════════════════════════════════

# Capital and position sizing
INITIAL_CAPITAL = 100000  # ₹1,00,000
POSITION_SIZE_PCT = 0.05  # 5% = ₹5,000 per position

# Supertrend parameters
SUPERTREND_PERIOD = 12
SUPERTREND_FACTOR = 3.0

# VIX filter thresholds
VIX_LOW = 13.0   # Trade when VIX below this (low fear)
VIX_HIGH = 19.0  # Trade when VIX above this (high fear)

# ATR% filter
ATR_PCT_MIN = 3.0  # Minimum ATR% for entry

# Max positions (to diversify risk)
MAX_POSITIONS = 20

# Files - Use home directory for persistence across Groww Cloud restarts
# Fallback to /tmp if HOME is not set (Groww Cloud environment)
HOME_DIR = os.path.expanduser("~")
if HOME_DIR == "/" or not HOME_DIR:
    HOME_DIR = "/tmp"
POSITIONS_FILE = os.path.join(HOME_DIR, ".groww_supertrend_positions.json")
SIGNALS_LOG_FILE = os.path.join(HOME_DIR, f".groww_supertrend_log_{datetime.now().strftime('%Y-%m-%d')}.json")

# ═══════════════════════════════════════════════════════════════════════════════
# STOCK UNIVERSE (299 stocks with Win Rate >= 40% from backtests)
# ═══════════════════════════════════════════════════════════════════════════════

SYMBOLS = [
    "360ONE", "AARTIIND", "ABCAPITAL", "ABSLAMC", "ACE", "ADANIENSOL", "ADANIENT",
    "ADANIGREEN", "ADANIPORTS", "ADANIPOWER", "AFFLE", "AIAENG", "AJANTPHARM",
    "AKZOINDIA", "ALIVUS", "AMBUJACEM", "ANANDRATHI", "ANANTRAJ", "ANGELONE",
    "ANURAS", "APARINDS", "APOLLO", "ASAHIINDIA", "ASHOKLEY", "ASIANPAINT",
    "ASTERDM", "ASTRAL", "ASTRAMICRO", "ATGL", "ATUL", "AUBANK", "AUROPHARMA",
    "AXISBANK", "BAJAJ-AUTO", "BAJAJFINSV", "BAJAJHLDNG", "BAJFINANCE", "BALKRISIND",
    "BANDHANBNK", "BASF", "BBOX", "BDL", "BEL", "BEML", "BHARATFORG", "BHARTIARTL",
    "BHEL", "BIKAJI", "BLS", "BLUESTARCO", "BORORENEW", "BRIGADE", "BSE", "BSOFT",
    "CAPLIPOINT", "CARBORUNIV", "CCL", "CEATLTD", "CENTURYPLY", "CESC", "CGCL",
    "CGPOWER", "CHALET", "CHAMBLFERT", "CHENNPETRO", "CHOICEIN", "CHOLAHLDNG",
    "CIPLA", "COCHINSHIP", "COFORGE", "CONCOR", "COROMANDEL", "CRAFTSMAN",
    "CREDITACC", "CRISIL", "CROMPTON", "DALBHARAT", "DATAPATTNS", "DCMSHRIRAM",
    "DEEPAKFERT", "DEEPAKNTR", "DELHIVERY", "DIVISLAB", "DIXON", "DRREDDY",
    "ECLERX", "EDELWEISS", "EICHERMOT", "EIHOTEL", "ELECON", "ENDURANCE", "ESCORTS",
    "ETERNAL", "EXIDEIND", "FACT", "FINCABLES", "FINEORG", "FINPIPE", "FORCEMOT",
    "FSL", "GAIL", "GALLANTT", "GENUSPOWER", "GESHIP", "GLAXO", "GLENMARK",
    "GMRP&UI", "GODREJCP", "GPIL", "GRASIM", "GRAVITA", "GRSE", "GUJGASLTD",
    "GVT&D", "HAL", "HATSUN", "HAVELLS", "HBLENGINE", "HCG", "HCLTECH", "HDFCAMC",
    "HEG", "HEXT", "HINDALCO", "HINDZINC", "HOMEFIRST", "HONASA", "HSCL",
    "IDFCFIRSTB", "IEX", "IGL", "IIFL", "IIFLCAPS", "INDHOTEL", "INDIANB",
    "INGERRAND", "INOXGREEN", "INOXWIND", "INTELLECT", "IRCON", "IRCTC", "IRFC",
    "J&KBANK", "JBCHEPHARM", "JBMA", "JINDALSTEL", "JIOFIN", "JKCEMENT", "JKLAKSHMI",
    "JKTYRE", "JSL", "JSWHL", "JSWSTEEL", "JUBLFOOD", "JUBLINGREA", "JWL",
    "JYOTHYLAB", "KALYANKJIL", "KARURVYSYA", "KEI", "KIMS", "KIOCL", "KIRLOSBROS",
    "KIRLOSENG", "KOTAKBANK", "KPIL", "KPITTECH", "KSB", "LEMONTREE", "LINDEINDIA",
    "LLOYDSME", "LODHA", "LTFOODS", "LTIM", "LTTS", "LUPIN", "M&M", "M&MFIN",
    "MAHABANK", "MANAPPURAM", "MANKIND", "MANYAVAR", "MARICO", "MAXHEALTH",
    "MAZDOCK", "MEDANTA", "METROBRAND", "METROPOLIS", "MINDACORP", "MMTC",
    "MOTILALOFS", "MPHASIS", "MSUMI", "NATCOPHARM", "NAUKRI", "NAVA", "NAVINFLUOR",
    "NAZARA", "NCC", "NETWEB", "NEULANDLAB", "NEWGEN", "NH", "NHPC", "NMDC",
    "NSLNISP", "OBEROIRLTY", "OIL", "PARADEEP", "PAYTM", "PCBL", "PERSISTENT",
    "PFIZER", "PGEL", "PGHL", "PHOENIXLTD", "PNBHOUSING", "POLYCAB", "POWERINDIA",
    "PPLPHARMA", "PRESTIGE", "PRIVISCL", "PRUDENT", "RADICO", "RAILTEL", "RAINBOW",
    "RAMCOCEM", "RATNAMANI", "RELIGARE", "RPOWER", "RVNL", "SAFARI", "SANOFI",
    "SAPPHIRE", "SARDAEN", "SBICARD", "SBILIFE", "SBIN", "SCHAEFFLER", "SCHNEIDER",
    "SHAILY", "SHAKTIPUMP", "SHRIPISTON", "SIEMENS", "SOBHA", "SOLARINDS",
    "SONATSOFTW", "SPLPETRO", "SRF", "STARCEMENT", "SUMICHEM", "SUNDRMFAST",
    "SWANCORP", "TARIL", "TATACHEM", "TATACOMM", "TATACONSUM", "TATAELXSI",
    "TATAINVEST", "TATAPOWER", "TATASTEEL", "TCI", "TDPOWERSYS", "TECHM",
    "TECHNOE", "TEGA", "TEJASNET", "THERMAX", "TIINDIA", "TIMETECHNO", "TIMKEN",
    "TITAGARH", "TITAN", "TMPV", "TORNTPHARM", "TRENT", "TRIDENT", "TRITURBINE",
    "TTML", "TVSMOTOR", "UJJIVANSFB", "UNITDSPR", "UNOMINDA", "UPL", "USHAMART",
    "UTIAMC", "VBL", "VEDL", "VESUVIUS", "VGUARD", "VINATIORGA", "VOLTAS", "VTL",
    "WABAG", "WESTLIFE", "WHIRLPOOL", "ZENSARTECH", "ZYDUSLIFE", "ZYDUSWELL",
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


def get_ltp(symbol: str) -> float:
    """Get last traded price for a symbol. Returns 0 on failure."""
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


def get_india_vix() -> Optional[float]:
    """
    Get current India VIX value from Groww.
    
    India VIX is an index - try multiple symbol formats.
    Returns None if unavailable.
    """
    # Try multiple possible symbols for India VIX
    vix_symbols = ["INDIA VIX", "INDIAVIX", "NIFTY VIX"]
    
    for symbol in vix_symbols:
        try:
            # Try LTP first
            resp = groww.get_ltp(
                segment=groww.SEGMENT_CASH,
                exchange_trading_symbols=f"NSE_{symbol}",
            )
            vix = resp.get(f"NSE_{symbol}", 0)
            if vix and float(vix) > 0:
                return float(vix)
        except Exception:
            pass
        
        try:
            # Try quote method
            resp = groww.get_quote(
                exchange=groww.EXCHANGE_NSE,
                segment=groww.SEGMENT_CASH,
                trading_symbol=symbol,
            )
            if resp:
                vix = resp.get("last_price") or resp.get("close") or resp.get("ohlc", {}).get("close", 0)
                if vix and float(vix) > 0:
                    return float(vix)
        except Exception:
            pass
    
    # Fallback: Get VIX from historical candles
    try:
        end = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        start = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
        
        resp = groww.get_historical_candles(
            exchange=groww.EXCHANGE_NSE,
            segment=groww.SEGMENT_CASH,
            groww_symbol="NSE-INDIA VIX",
            start_time=start,
            end_time=end,
            candle_interval=groww.CANDLE_INTERVAL_DAY,
        )
        candles = resp.get("candles", []) if resp else []
        if candles and len(candles) > 0:
            # Get last candle's close (index 4)
            last_candle = candles[-1]
            if len(last_candle) >= 5:
                return float(last_candle[4])  # Close price
    except Exception:
        pass
    
    return None


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


def get_daily_candles(symbol: str, days: int = 60, max_retries: int = 3) -> List[Dict]:
    """
    Get historical daily candles for a symbol with retry logic.
    
    Returns list of dicts with keys: timestamp, open, high, low, close, volume
    Empty list on failure.
    
    Note: Groww returns candles as:
    [timestamp_str, open, high, low, close, volume, oi]
    where timestamp_str is "YYYY-MM-DDTHH:mm:ss" format
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
            
            if not resp:
                return []
            
            raw_candles = resp.get("candles", [])
            if not raw_candles:
                return []
            
            candles = []
            for c in raw_candles:
                if not c or len(c) < 5:
                    continue
                
                # Parse candle: [timestamp_str, open, high, low, close, volume, oi]
                try:
                    timestamp = c[0]  # String like "2025-09-24T10:30:00"
                    open_price = float(c[1])
                    high_price = float(c[2])
                    low_price = float(c[3])
                    close_price = float(c[4])
                    volume = int(c[5]) if len(c) > 5 and c[5] else 0
                    
                    # Validate prices
                    if open_price > 0 and high_price > 0 and low_price > 0 and close_price > 0:
                        candles.append({
                            "timestamp": timestamp,
                            "open": open_price,
                            "high": high_price,
                            "low": low_price,
                            "close": close_price,
                            "volume": volume,
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


def get_holdings() -> Dict[str, Dict]:
    """
    Get current CNC holdings.
    
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
        qty: Quantity to buy/sell
        txn_type: groww.TRANSACTION_TYPE_BUY or groww.TRANSACTION_TYPE_SELL
    
    Returns:
        Order response dict with groww_order_id and order_status
    
    Raises:
        Exception on failure
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
    position_value = INITIAL_CAPITAL * POSITION_SIZE_PCT  # ₹5,000
    return max(1, int(position_value / price))


# ═══════════════════════════════════════════════════════════════════════════════
# INDICATOR CALCULATIONS
# ═══════════════════════════════════════════════════════════════════════════════


def calculate_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 12) -> List[float]:
    """
    Calculate Average True Range (ATR) using Wilder's smoothing.
    
    Returns list of ATR values (same length as input, NaN for early bars).
    """
    n = len(closes)
    if n < 2:
        return [np.nan] * n
    
    # Calculate True Range
    tr = [highs[0] - lows[0]]  # First TR is just H-L
    for i in range(1, n):
        tr.append(max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        ))
    
    # Calculate ATR with Wilder's smoothing
    atr = [np.nan] * n
    if n >= period:
        # First ATR is SMA of first 'period' TRs
        atr[period - 1] = sum(tr[:period]) / period
        
        # Subsequent ATRs use Wilder's smoothing: ATR = (prev_ATR * (period-1) + TR) / period
        for i in range(period, n):
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    
    return atr


def calculate_supertrend(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    period: int = 12,
    factor: float = 3.0
) -> Dict[str, List[float]]:
    """
    Calculate Supertrend indicator.
    
    Returns:
        dict with 'supertrend' and 'direction' lists
        direction: -1 = uptrend (green/bullish), +1 = downtrend (red/bearish)
    """
    n = len(closes)
    atr = calculate_atr(highs, lows, closes, period)
    
    supertrend = [np.nan] * n
    direction = [np.nan] * n
    
    # Upper and lower bands
    final_upper = [np.nan] * n
    final_lower = [np.nan] * n
    
    for i in range(n):
        if np.isnan(atr[i]):
            continue
        
        hl2 = (highs[i] + lows[i]) / 2
        basic_upper = hl2 + factor * atr[i]
        basic_lower = hl2 - factor * atr[i]
        
        # First valid bar
        if i == 0 or np.isnan(final_upper[i - 1]):
            final_upper[i] = basic_upper
            final_lower[i] = basic_lower
            # Initialize direction based on close vs bands
            if closes[i] > basic_lower:
                direction[i] = -1  # Uptrend
                supertrend[i] = basic_lower
            else:
                direction[i] = 1  # Downtrend
                supertrend[i] = basic_upper
            continue
        
        # Adjust upper band: can only move down or stay same
        if basic_upper < final_upper[i - 1] or closes[i - 1] > final_upper[i - 1]:
            final_upper[i] = basic_upper
        else:
            final_upper[i] = final_upper[i - 1]
        
        # Adjust lower band: can only move up or stay same
        if basic_lower > final_lower[i - 1] or closes[i - 1] < final_lower[i - 1]:
            final_lower[i] = basic_lower
        else:
            final_lower[i] = final_lower[i - 1]
        
        # Determine direction based on previous direction and close vs bands
        prev_dir = direction[i - 1] if not np.isnan(direction[i - 1]) else -1
        
        if prev_dir == -1:  # Was uptrend
            if closes[i] < final_lower[i]:
                direction[i] = 1  # Flip to downtrend
                supertrend[i] = final_upper[i]
            else:
                direction[i] = -1  # Stay uptrend
                supertrend[i] = final_lower[i]
        else:  # Was downtrend
            if closes[i] > final_upper[i]:
                direction[i] = -1  # Flip to uptrend
                supertrend[i] = final_lower[i]
            else:
                direction[i] = 1  # Stay downtrend
                supertrend[i] = final_upper[i]
    
    return {"supertrend": supertrend, "direction": direction}


def analyze_stock(symbol: str, vix: Optional[float]) -> Dict[str, Any]:
    """
    Analyze a stock and return signal based on YESTERDAY's close.
    
    At 9:15 AM, we analyze the completed daily bars (yesterday = last bar).
    We check if yesterday had a Supertrend flip.
    
    Returns:
        dict with 'action' ('BUY', 'SELL', 'HOLD', None), 'reason', and metadata
    """
    candles = get_daily_candles(symbol, days=60)
    
    if len(candles) < 15:  # Need at least 15 bars for reliable Supertrend
        return {"action": None, "reason": "Insufficient data", "data": {}}
    
    # Extract OHLC from candles
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    closes = [c["close"] for c in candles]
    
    # Calculate Supertrend
    st = calculate_supertrend(highs, lows, closes, SUPERTREND_PERIOD, SUPERTREND_FACTOR)
    directions = st["direction"]
    supertrends = st["supertrend"]
    
    # Find last two valid direction values (yesterday and day before)
    valid_indices = [i for i, d in enumerate(directions) if not np.isnan(d)]
    
    if len(valid_indices) < 2:
        return {"action": None, "reason": "Insufficient Supertrend data", "data": {}}
    
    # Yesterday = last completed bar
    idx_yesterday = valid_indices[-1]
    idx_prev = valid_indices[-2]
    
    dir_yesterday = directions[idx_yesterday]
    dir_prev = directions[idx_prev]
    st_yesterday = supertrends[idx_yesterday]
    close_yesterday = closes[idx_yesterday]
    
    # Check for trend flips
    flip_to_uptrend = dir_prev > 0 and dir_yesterday < 0  # Red to Green
    flip_to_downtrend = dir_prev < 0 and dir_yesterday > 0  # Green to Red
    is_uptrend = dir_yesterday < 0
    
    # Prepare metadata
    data = {
        "close": close_yesterday,
        "supertrend": st_yesterday,
        "direction": "UP" if is_uptrend else "DOWN",
        "flip": "TO_UP" if flip_to_uptrend else ("TO_DOWN" if flip_to_downtrend else None),
    }
    
    # ========== EXIT SIGNAL (Supertrend flipped to downtrend) ==========
    if flip_to_downtrend:
        return {
            "action": "SELL",
            "reason": f"Supertrend flip to downtrend (ST={st_yesterday:.2f})",
            "data": data,
        }
    
    # ========== ENTRY SIGNAL (Supertrend flipped to uptrend + filters) ==========
    if flip_to_uptrend:
        # Check VIX filter
        if vix is not None and vix > 0:
            vix_pass = (vix < VIX_LOW) or (vix > VIX_HIGH)
            if not vix_pass:
                return {
                    "action": None,
                    "reason": f"VIX filter blocked: VIX={vix:.2f} in neutral zone [{VIX_LOW}-{VIX_HIGH}]",
                    "data": data,
                }
        else:
            # If VIX unavailable, still allow entry but log warning
            print(f"   ⚠️ {symbol}: VIX unavailable, allowing entry")
        
        # Check ATR% filter
        atr = calculate_atr(highs, lows, closes, SUPERTREND_PERIOD)
        atr_yesterday = atr[idx_yesterday] if not np.isnan(atr[idx_yesterday]) else 0
        atr_pct = (atr_yesterday / close_yesterday * 100) if close_yesterday > 0 else 0
        
        data["atr_pct"] = atr_pct
        
        if atr_pct < ATR_PCT_MIN:
            return {
                "action": None,
                "reason": f"ATR% filter blocked: ATR%={atr_pct:.2f}% < {ATR_PCT_MIN}%",
                "data": data,
            }
        
        # All filters passed
        vix_str = f"VIX={vix:.2f}" if vix else "VIX=N/A"
        return {
            "action": "BUY",
            "reason": f"Supertrend flip to uptrend | {vix_str} | ATR%={atr_pct:.2f}%",
            "data": data,
        }
    
    # No flip - check current state
    if is_uptrend:
        return {"action": "HOLD", "reason": "In uptrend, holding", "data": data}
    else:
        return {"action": None, "reason": "In downtrend, no position", "data": data}


# ═══════════════════════════════════════════════════════════════════════════════
# TIME CHECK
# ═══════════════════════════════════════════════════════════════════════════════

now = datetime.now()
h, m = now.hour, now.minute

# Entry window: 9:15-9:30 AM
is_entry_window = h == 9 and 15 <= m <= 30

# Market hours check
is_market = (h == 9 and m >= 15) or (10 <= h <= 14) or (h == 15 and m <= 30)

print(f"\n⏰ {now.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"   Entry Window: {is_entry_window} | Market Hours: {is_market}")

if not is_market:
    print("⛔ Outside market hours, exiting")
    raise SystemExit(0)

if not is_entry_window:
    print("⏸️ Outside entry window (9:15-9:30 AM), exiting")
    print("   This strategy runs daily at 9:15-9:30 AM to process yesterday's signals")
    raise SystemExit(0)

# ═══════════════════════════════════════════════════════════════════════════════
# FETCH VIX
# ═══════════════════════════════════════════════════════════════════════════════

print("\n📊 Fetching India VIX...")
vix = get_india_vix()

if vix is not None and vix > 0:
    if vix < VIX_LOW:
        vix_status = "LOW FEAR ✅"
    elif vix > VIX_HIGH:
        vix_status = "HIGH FEAR ✅"
    else:
        vix_status = f"NEUTRAL ⚠️ (blocks entries)"
    
    print(f"   VIX = {vix:.2f} ({vix_status})")
else:
    print("   ⚠️ Could not fetch VIX - entries will proceed without VIX filter")
    vix = None

# ═══════════════════════════════════════════════════════════════════════════════
# GET CURRENT HOLDINGS
# ═══════════════════════════════════════════════════════════════════════════════

print("\n📁 Fetching current holdings...")
holdings = get_holdings()
tracked = load_json(POSITIONS_FILE, {})

# Filter holdings to only our strategy symbols
strategy_holdings = {s: h for s, h in holdings.items() if s in SYMBOLS}
print(f"   Strategy positions: {len(strategy_holdings)}")

if strategy_holdings:
    print("   Current positions:")
    for sym, h in list(strategy_holdings.items())[:10]:  # Show first 10
        ltp = get_ltp(sym)
        entry = tracked.get(sym, {}).get("entry", h["avg"])
        pnl = ((ltp - entry) / entry * 100) if entry > 0 and ltp > 0 else 0
        print(f"      {sym}: {h['qty']} @ ₹{entry:.2f} → ₹{ltp:.2f} ({pnl:+.2f}%)")
        time.sleep(0.05)
    if len(strategy_holdings) > 10:
        print(f"      ... and {len(strategy_holdings) - 10} more")

# ═══════════════════════════════════════════════════════════════════════════════
# PROCESS EXITS (Supertrend flip to red)
# ═══════════════════════════════════════════════════════════════════════════════

print(f"\n📤 Processing exits for {len(strategy_holdings)} positions...")
exits = 0
exit_log = []

for sym, holding in strategy_holdings.items():
    time.sleep(0.15)  # Rate limiting
    signal = analyze_stock(sym, vix)
    
    if signal["action"] == "SELL":
        try:
            ltp = get_ltp(sym)
            entry = tracked.get(sym, {}).get("entry", holding["avg"])
            pnl = ((ltp - entry) / entry * 100) if entry > 0 and ltp > 0 else 0
            
            order = place_order(sym, holding["qty"], groww.TRANSACTION_TYPE_SELL)
            oid = order.get("groww_order_id", "N/A")
            status = order.get("order_status", "UNKNOWN")
            
            print(f"   ✅ SELL {sym}: {holding['qty']} @ ₹{ltp:.2f} | P&L: {pnl:+.2f}% | {signal['reason']} [{oid}:{status}]")
            
            exit_log.append({
                "symbol": sym,
                "qty": holding["qty"],
                "entry": entry,
                "exit": ltp,
                "pnl_pct": pnl,
                "reason": signal["reason"],
                "order_id": oid,
            })
            
            # Remove from tracked positions
            if sym in tracked:
                del tracked[sym]
            
            exits += 1
        except Exception as e:
            print(f"   ❌ {sym}: Failed to sell - {e}")
        
        time.sleep(0.3)

save_json(POSITIONS_FILE, tracked)
print(f"   Exits: {exits}")

# ═══════════════════════════════════════════════════════════════════════════════
# PROCESS ENTRIES (Supertrend flip to green + filters pass)
# ═══════════════════════════════════════════════════════════════════════════════

# Get fresh holdings after exits
holdings = get_holdings()
strategy_holdings = {s: h for s, h in holdings.items() if s in SYMBOLS}
current_positions = len(strategy_holdings)
available_slots = MAX_POSITIONS - current_positions

print(f"\n📈 Processing entries (Available slots: {available_slots}/{MAX_POSITIONS})...")

entries = 0  # Initialize to prevent NameError
entry_log = []

if available_slots <= 0:
    print("   ⚠️ Max positions reached, skipping entries")
else:
    buy_candidates = []
    scanned = 0
    
    for sym in SYMBOLS:
        # Skip if already holding
        if sym in strategy_holdings:
            continue
        
        # Skip if already tracked (prevents duplicate entries)
        if sym in tracked:
            continue
        
        time.sleep(0.15)  # Rate limiting
        scanned += 1
        
        if scanned % 50 == 0:
            print(f"   Scanned {scanned}/{len(SYMBOLS) - len(strategy_holdings)} stocks...")
        
        signal = analyze_stock(sym, vix)
        
        if signal["action"] == "BUY":
            ltp = get_ltp(sym)
            if ltp > 0:
                buy_candidates.append({
                    "symbol": sym,
                    "ltp": ltp,
                    "reason": signal["reason"],
                    "data": signal.get("data", {}),
                })
                print(f"   🎯 {sym}: BUY signal @ ₹{ltp:.2f} | {signal['reason']}")
    
    print(f"\n   Scanned {scanned} stocks, found {len(buy_candidates)} buy signals")
    
    # Place orders for candidates (up to available slots)
    for candidate in buy_candidates[:available_slots]:
        sym = candidate["symbol"]
        ltp = candidate["ltp"]
        qty = calc_qty(ltp)
        
        if qty < 1:
            print(f"   ⏭️ {sym}: Qty too low at ₹{ltp:.2f}")
            continue
        
        try:
            order = place_order(sym, qty, groww.TRANSACTION_TYPE_BUY)
            oid = order.get("groww_order_id", "N/A")
            status = order.get("order_status", "UNKNOWN")
            
            # Track position
            tracked[sym] = {
                "entry": ltp,
                "qty": qty,
                "entry_date": datetime.now().isoformat(),
                "reason": candidate["reason"],
            }
            
            entry_log.append({
                "symbol": sym,
                "qty": qty,
                "entry": ltp,
                "reason": candidate["reason"],
                "order_id": oid,
            })
            
            print(f"   ✅ BUY {sym}: {qty} @ ₹{ltp:.2f} | Value: ₹{qty * ltp:,.0f} [{oid}:{status}]")
            entries += 1
        except Exception as e:
            print(f"   ❌ {sym}: Failed to buy - {e}")
        
        time.sleep(0.3)
    
    save_json(POSITIONS_FILE, tracked)
    print(f"   Entries: {entries}")

# ═══════════════════════════════════════════════════════════════════════════════
# SAVE LOG
# ═══════════════════════════════════════════════════════════════════════════════

log_data = {
    "timestamp": datetime.now().isoformat(),
    "vix": vix,
    "exits": exit_log,
    "entries": entry_log,
    "positions_count": len(tracked),
}
save_json(SIGNALS_LOG_FILE, log_data)

# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

# Final holdings count
final_holdings = get_holdings()
final_strategy = {s: h for s, h in final_holdings.items() if s in SYMBOLS}

print("\n" + "=" * 60)
print("📊 SUPERTREND VIX+ATR% STRATEGY SUMMARY")
print("=" * 60)
print(f"   VIX: {vix:.2f}" if vix else "   VIX: N/A")
print(f"   Exits: {exits}")
print(f"   Entries: {entries}")
print(f"   Active Positions: {len(final_strategy)}/{MAX_POSITIONS}")
print("=" * 60)

if final_strategy:
    print("\n📁 CURRENT POSITIONS:")
    total_value = 0
    total_pnl = 0
    
    for sym, h in list(final_strategy.items())[:15]:  # Show first 15
        ltp = get_ltp(sym)
        entry = tracked.get(sym, {}).get("entry", h["avg"])
        pnl = ((ltp - entry) / entry * 100) if entry > 0 and ltp > 0 else 0
        value = ltp * h["qty"]
        total_value += value
        total_pnl += pnl
        print(f"   {sym}: {h['qty']} @ ₹{entry:.2f} → ₹{ltp:.2f} ({pnl:+.2f}%) | ₹{value:,.0f}")
        time.sleep(0.05)
    
    if len(final_strategy) > 15:
        print(f"   ... and {len(final_strategy) - 15} more positions")
    
    avg_pnl = total_pnl / len(final_strategy) if final_strategy else 0
    print(f"\n   Total Position Value: ₹{total_value:,.0f}")
    print(f"   Average P&L: {avg_pnl:+.2f}%")

print("\n✅ Strategy execution complete")
print(f"   Log saved to: {SIGNALS_LOG_FILE}")
