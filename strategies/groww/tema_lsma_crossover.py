"""
TEMA-LSMA Crossover Strategy - CNC (Delivery)

Groww Cloud Schedule:
    - Runs daily 9:15 AM IST - 3:30 PM IST (full market hours)
      * 9:15-9:30: Entry phase (after market open with validated prices)
      * 9:30-3:30: Exit phase (continuous position management)
    - Entry: TEMA(25) crosses above LSMA(100) + filters pass (on next day open)
    - Exit: TEMA(25) crosses below LSMA(100) (on next day open)
    - Product: CNC (delivery, held in DEMAT)

Strategy:
    - TEMA(25) / LSMA(100) crossover for trend direction
    - ATR(14)% > 3.5% (minimum volatility filter)
    - ADX(28) > 25 (trend strength filter)
    - No stop loss (exit only on bearish crossunder)

Order Execution Improvements:
    - Uses limit orders with 0.5% tolerance for better fills
    - Tracks actual order fill price (not LTP at order time)
    - Fetches yesterday's close candles to avoid lookahead bias
    - Retry logic for failed order fills

Backtest Results (MAX period, No Stop):
    - Net P&L: 603.94%
    - IRR: 53.57%
    - Win Rate: 48.68%
    - Trades: 1,405

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

# MA parameters
TEMA_PERIOD = 25
LSMA_PERIOD = 100

# Entry filters
ATR_PERIOD = 14
ATR_PCT_MIN = 3.5  # ATR(14)% > 3.5%
ADX_PERIOD = 28
ADX_MIN = 25.0     # ADX(28) > 25

# Max positions (to diversify risk)
MAX_POSITIONS = 20

# Files - Use home directory for persistence across Groww Cloud restarts
HOME_DIR = os.path.expanduser("~")
if HOME_DIR == "/" or not HOME_DIR:
    HOME_DIR = "/tmp"
POSITIONS_FILE = os.path.join(HOME_DIR, ".groww_tema_lsma_positions.json")
SIGNALS_LOG_FILE = os.path.join(HOME_DIR, f".groww_tema_lsma_log_{datetime.now().strftime('%Y-%m-%d')}.json")

# ═══════════════════════════════════════════════════════════════════════════════
# STOCK UNIVERSE (Main basket - 563 stocks)
# Filter in production based on backtest win rate if needed
# ═══════════════════════════════════════════════════════════════════════════════

SYMBOLS = [
    "360ONE", "AARTIIND", "AAVAS", "ABB", "ABCAPITAL", "ABFRL", "ACC", "ACE",
    "ADANIENT", "ADANIENSOL", "ADANIGREEN", "ADANIPORTS", "ADANIPOWER", "AEGISLOG",
    "AFFLE", "AIAENG", "AJANTPHARM", "ALKYLAMINE", "ALOKINDS", "AMBER", "AMBUJACEM",
    "ANANDRATHI", "ANANTRAJ", "ANGELONE", "APARINDS", "APLAPOLLO", "APOLLO",
    "APOLLOHOSP", "APOLLOTYRE", "ARE&M", "ARVIND", "ASAHIINDIA", "ASHOKLEY",
    "ASTERDM", "ASTRAL", "ASTRAZEN", "ATGL", "ATUL", "AUBANK", "AUROPHARMA",
    "AVANTIFEED", "AWL", "AXISBANK", "BAJAJ-AUTO", "BAJAJFINSV", "BAJAJHLDNG",
    "BAJFINANCE", "BALKRISIND", "BALRAMCHIN", "BANCOINDIA", "BANDHANBNK",
    "BANKBARODA", "BANKINDIA", "BASF", "BATAINDIA", "BAYERCROP", "BBOX", "BBTC",
    "BDL", "BEL", "BEML", "BHARATFORG", "BHARTIHEXA", "BHEL", "BIKAJI", "BIRLACORPN",
    "BLACKBUCK", "BLUEDART", "BLUESTARCO", "BLS", "BORORENEW", "BPCL", "BRIGADE",
    "BRITANNIA", "BSE", "BSOFT", "CAMS", "CANFINHOME", "CAPLIPOINT", "CARBORUNIV",
    "CARTRADE", "CASTROLIND", "CCL", "CDSL", "CEATLTD", "CELLO", "CEMPRO",
    "CENTRALBK", "CENTURYPLY", "CESC", "CGCL", "CGPOWER", "CHALET", "CHAMBLFERT",
    "CHENNPETRO", "CHOICEIN", "CHOLAFIN", "CHOLAHLDNG", "CIPLA", "CLEAN",
    "COALINDIA", "COCHINSHIP", "COFORGE", "COLPAL", "CONCOR", "COROMANDEL",
    "CRAFTSMAN", "CREDITACC", "CRISIL", "CROMPTON", "CUB", "CUMMINSIND", "CYIENT",
    "DALBHARAT", "DCMSHRIRAM", "DEEPAKFERT", "DEEPAKNTR", "DELHIVERY", "DEVYANI",
    "DIVISLAB", "DIXON", "DLF", "DMART", "DOMS", "DRREDDY", "ECLERX", "EDELWEISS",
    "EICHERMOT", "EIDPARRY", "EIHOTEL", "ELECON", "ELGIEQUIP", "EMAMILTD", "EMCURE",
    "ENDURANCE", "ENGINERSIN", "ERIS", "ESCORTS", "ETERNAL", "EXIDEIND", "FACT",
    "FEDERALBNK", "FINCABLES", "FINEORG", "FINPIPE", "FLUOROCHEM", "FORCEMOT",
    "FORTIS", "FSL", "GABRIEL", "GAIL", "GALLANTT", "GENUSPOWER", "GESHIP", "GICRE",
    "GLAND", "GLAXO", "GLENMARK", "GMDCLTD", "GMRAIRPORT", "GMRP&UI", "GODFRYPHLP",
    "GODREJAGRO", "GODREJCP", "GODREJIND", "GODIGIT", "GPIL", "GPPL", "GRANULES",
    "GRAPHITE", "GRASIM", "GRAVITA", "GRINDWELL", "GRINFRA", "GRSE", "GUJGASLTD",
    "GVT&D", "HAL", "HATSUN", "HAVELLS", "HBLENGINE", "HCG", "HCLTECH", "HDFCAMC",
    "HDFCBANK", "HDFCLIFE", "HEG", "HEROMOTOCO", "HEXT", "HFCL", "HINDALCO",
    "HINDCOPPER", "HOMEFIRST", "HONASA", "HSCL", "HUDCO", "ICICIBANK", "IDBI",
    "IDFCFIRSTB", "IEX", "IFCI", "IGL", "IIFL", "IIFLCAPS", "INDHOTEL", "INDIACEM",
    "INDIAMART", "INDIANB", "INDIGO", "INDUSINDBK", "INDUSTOWER", "INGERRAND",
    "INOXWIND", "INTELLECT", "IOB", "IOC", "IPCALAB", "IRCON", "IRCTC", "IREDA",
    "IRB", "IRFC", "ITC", "ITI", "IXIGO", "J&KBANK", "JBCHEPHARM", "JBMA", "JIOFIN",
    "JINDALSAW", "JINDALSTEL", "JKCEMENT", "JKLAKSHMI", "JKTYRE", "JMFINANCIL",
    "JPPOWER", "JSL", "JSWENERGY", "JSWHL", "JSWSTEEL", "JUBLFOOD", "JUBLINGREA",
    "JUBLPHARMA", "JWL", "JYOTHYLAB", "KAJARIACER", "KALYANKJIL", "KANSAINER",
    "KARURVYSYA", "KAYNES", "KEC", "KEI", "KFINTECH", "KIMS", "KIOCL", "KIRLOSBROS",
    "KIRLOSENG", "KOTAKBANK", "KPIL", "KPIGREEN", "KPITTECH", "KPRMILL", "KRBL",
    "KSB", "LALPATHLAB", "LAURUSLABS", "LEMONTREE", "LICHSGFIN", "LINDEINDIA",
    "LMW", "LT", "LTFOODS", "LTIM", "LTTS", "LUPIN", "M&M", "M&MFIN", "MAHABANK",
    "MANAPPURAM", "MANKIND", "MANYAVAR", "MAPMYINDIA", "MARICO", "MAXHEALTH",
    "MCX", "MEDANTA", "MEDPLUS", "METROPOLIS", "MFSL", "MGL", "MINDACORP", "MMTC",
    "MOTILALOFS", "MPHASIS", "MRPL", "MSUMI", "MUTHOOTFIN", "NATIONALUM",
    "NATCOPHARM", "NAUKRI", "NAVA", "NAVINFLUOR", "NAZARA", "NBCC", "NCC", "NESCO",
    "NETWEB", "NEULANDLAB", "NEWGEN", "NH", "NHPC", "NIACL", "NLCINDIA", "NMDC",
    "NTPC", "NUVAMA", "NUVOCO", "NYKAA", "OBEROIRLTY", "OFSS", "OIL", "OLECTRA",
    "ONGC", "PARADEEP", "PAYTM", "PCBL", "PERSISTENT", "PETRONET", "PFC", "PFIZER",
    "PGEL", "PGHL", "PHOENIXLTD", "PIDILITIND", "PIIND", "PNB", "PNBHOUSING",
    "POLYCAB", "POLYMED", "PPLPHARMA", "POWERINDIA", "PRESTIGE", "PRIVISCL",
    "PRUDENT", "PSB", "RADICO", "RAILTEL", "RAINBOW", "RAMCOCEM", "RATNAMANI",
    "RBLBANK", "RECLTD", "REDINGTON", "RELAXO", "RELIGARE", "RELIANCE", "RHIM",
    "RKFORGE", "RPOWER", "RRKABEL", "RVNL", "SAFARI", "SAIL", "SANSERA", "SAPPHIRE",
    "SARDAEN", "SBIN", "SBICARD", "SBILIFE", "SCHAEFFLER", "SCHNEIDER", "SCI",
    "SHAILY", "SHAKTIPUMP", "SHRIRAMFIN", "SHRIPISTON", "SHYAMMETL", "SIEMENS",
    "SJVN", "SOBHA", "SOLARINDS", "SONACOMS", "SONATSOFTW", "SPLPETRO", "SRF",
    "STAR", "STARCEMENT", "SUNDARMFIN", "SUNDRMFAST", "SUNTV", "SUNPHARMA",
    "SUPREMEIND", "SUZLON", "SWANCORP", "SWIGGY", "SYNGENE", "SYRMA", "TARIL",
    "TATACHEM", "TATACOMM", "TATACONSUM", "TATAELXSI", "TATAINVEST", "TATAPOWER",
    "TATASTEEL", "TATATECH", "TCI", "TDPOWERSYS", "TECHM", "TECHNOE", "TEGA",
    "TEJASNET", "THANGAMAYL", "THERMAX", "TI", "TIINDIA", "TIMKEN", "TIMETECHNO",
    "TITAGARH", "TITAN", "TMPV", "TORNTPOWER", "TRENT", "TRIDENT", "TRITURBINE",
    "TTKPRESTIG", "TTML", "TVSMOTOR", "UBL", "UCOBANK", "UJJIVANSFB", "UNIONBANK",
    "UPL", "USHAMART", "UTIAMC", "VARROC", "VBL", "VEDL", "VESUVIUS", "VGUARD",
    "VIJAYA", "VINATIORGA", "VOLTAS", "VTL", "WABAG", "WELCORP", "WELSPUNLIV",
    "WESTLIFE", "WHIRLPOOL", "WIPRO", "WOCKPHARMA", "ZENTEC", "ZENSARTECH",
    "ZFCVINDIA", "ZYDUSLIFE", "ZYDUSWELL",
]

# ═══════════════════════════════════════════════════════════════════════════════
# INITIALIZE API (TOTP Flow with Retry)
# ═══════════════════════════════════════════════════════════════════════════════

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
    network_errors = ['timeout', 'connection', 'connect', 'max retries', 'temporarily unavailable']
    if any(x in error_lower for x in network_errors):
        return True
    if any(x in error_lower for x in ['502', '503', '504', '500']):
        return True
    if any(code in error_msg for code in RETRYABLE_ERRORS):
        return True
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
                wait_time = retry_delay * attempt
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


def get_daily_candles(symbol: str, days: int = 150, exclude_today: bool = True) -> List[Dict]:
    """
    Get historical daily candles for a symbol.
    Need 150 days for LSMA(100) warmup.
    
    Args:
        symbol: Stock symbol
        days: Number of days of history to fetch
        exclude_today: If True, exclude today's in-progress candle to avoid lookahead bias
    
    Returns:
        List of candles with OHLC data
    """
    try:
        end = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        
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
        
        # Parse candles
        candles = []
        today_date = datetime.now().strftime("%Y-%m-%d")
        
        for c in raw_candles:
            ts = c.get("timestamp")
            if not ts:
                continue
            
            try:
                # Parse timestamp and extract date
                candle_date = ts.split(" ")[0] if " " in ts else ts.split("T")[0]
                
                # Skip today's candle if exclude_today is True (to avoid lookahead bias)
                if exclude_today and candle_date == today_date:
                    continue
                
                candle = {
                    "timestamp": ts,
                    "date": candle_date,
                    "open": float(c.get("open", 0)),
                    "high": float(c.get("high", 0)),
                    "low": float(c.get("low", 0)),
                    "close": float(c.get("close", 0)),
                    "volume": float(c.get("volume", 0)),
                }
                candles.append(candle)
            except (ValueError, TypeError, KeyError):
                continue
        
        return candles
    
    except Exception as e:
        print(f"   ⚠️ Candles error for {symbol}: {e}")
        return []
        
        candles = []
        for c in raw_candles:
            if not c or len(c) < 5:
                continue
            try:
                timestamp = c[0]
                open_price = float(c[1])
                high_price = float(c[2])
                low_price = float(c[3])
                close_price = float(c[4])
                volume = int(c[5]) if len(c) > 5 and c[5] else 0
                
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
        print(f"   ⚠️ Candles error for {symbol}: {e}")
        return []


def get_holdings() -> Dict[str, Dict]:
    """Get current CNC holdings."""
    try:
        resp = groww.get_holdings_for_user()
        holdings = {}
        
        for h in resp.get("holdings", []):
            symbol = h.get("trading_symbol")
            qty = h.get("quantity", 0)
            avg = h.get("average_price", 0)
            
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


def place_order(symbol: str, qty: int, txn_type: str, price: float = None, is_limit: bool = True) -> Dict:
    """
    Place CNC order with optional limit price for better fills.
    
    Args:
        symbol: Stock symbol
        qty: Quantity to trade
        txn_type: BUY or SELL
        price: Reference price for limit order (uses 0.5% tolerance band)
        is_limit: If True, use limit order; if False, use market order (fallback)
    
    Returns:
        Order response dict with order_id and actual fill info
    """
    if is_limit and price and price > 0:
        # Use limit order with 0.5% tolerance band
        # For BUY: set limit slightly above market (0.5% higher)
        # For SELL: set limit slightly below market (0.5% lower)
        tolerance_pct = 0.005  # 0.5%
        
        if txn_type == groww.TRANSACTION_TYPE_BUY:
            limit_price = price * (1 + tolerance_pct)  # 0.5% above current
        else:  # SELL
            limit_price = price * (1 - tolerance_pct)  # 0.5% below current
        
        try:
            return groww.place_order(
                trading_symbol=symbol,
                exchange=groww.EXCHANGE_NSE,
                segment=groww.SEGMENT_CASH,
                transaction_type=txn_type,
                order_type=groww.ORDER_TYPE_LIMIT,
                product=groww.PRODUCT_CNC,
                quantity=qty,
                price=limit_price,
                validity=groww.VALIDITY_DAY,
            )
        except Exception as e:
            print(f"      ⚠️ Limit order failed, retrying as market order: {e}")
            return place_order(symbol, qty, txn_type, price=None, is_limit=False)
    
    # Fallback to market order (no price specified)
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
    position_value = INITIAL_CAPITAL * POSITION_SIZE_PCT
    return max(1, int(position_value / price))


# ═══════════════════════════════════════════════════════════════════════════════
# INDICATOR CALCULATIONS
# ═══════════════════════════════════════════════════════════════════════════════


def calculate_ema(values: List[float], period: int) -> List[float]:
    """Calculate EMA using standard formula."""
    n = len(values)
    ema = [np.nan] * n
    if n < period:
        return ema
    
    # First EMA is SMA
    ema[period - 1] = sum(values[:period]) / period
    
    # EMA formula: EMA = (Close - prev_EMA) * multiplier + prev_EMA
    multiplier = 2 / (period + 1)
    for i in range(period, n):
        ema[i] = (values[i] - ema[i - 1]) * multiplier + ema[i - 1]
    
    return ema


def calculate_tema(closes: List[float], period: int) -> List[float]:
    """Calculate Triple EMA: 3*EMA1 - 3*EMA2 + EMA3."""
    ema1 = calculate_ema(closes, period)
    
    # EMA of EMA1 (filter out NaN)
    ema1_valid = [v if not np.isnan(v) else 0.0 for v in ema1]
    ema2 = calculate_ema(ema1_valid, period)
    
    # EMA of EMA2
    ema2_valid = [v if not np.isnan(v) else 0.0 for v in ema2]
    ema3 = calculate_ema(ema2_valid, period)
    
    # TEMA = 3*EMA1 - 3*EMA2 + EMA3
    n = len(closes)
    tema = [np.nan] * n
    for i in range(n):
        if not np.isnan(ema1[i]) and not np.isnan(ema2[i]) and not np.isnan(ema3[i]):
            tema[i] = 3 * ema1[i] - 3 * ema2[i] + ema3[i]
    
    return tema


def calculate_lsma(closes: List[float], period: int) -> List[float]:
    """Calculate Least Squares Moving Average (Linear Regression)."""
    n = len(closes)
    lsma = [np.nan] * n
    if n < period:
        return lsma
    
    # Precompute x statistics
    x = np.arange(period, dtype=float)
    x_mean = (period - 1) / 2.0
    x_var = np.sum((x - x_mean) ** 2)
    
    for i in range(period - 1, n):
        y = closes[i - period + 1:i + 1]
        y_mean = np.mean(y)
        slope = np.sum((x - x_mean) * (np.array(y) - y_mean)) / x_var
        lsma[i] = slope * (period - 1) + (y_mean - slope * x_mean)
    
    return lsma


def calculate_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> List[float]:
    """Calculate ATR using Wilder's smoothing."""
    n = len(closes)
    if n < 2:
        return [np.nan] * n
    
    # Calculate True Range
    tr = [highs[0] - lows[0]]
    for i in range(1, n):
        tr.append(max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        ))
    
    # Calculate ATR with Wilder's smoothing
    atr = [np.nan] * n
    if n >= period:
        atr[period - 1] = sum(tr[:period]) / period
        for i in range(period, n):
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    
    return atr


def calculate_adx(highs: List[float], lows: List[float], closes: List[float], period: int = 28) -> List[float]:
    """Calculate ADX (Average Directional Index)."""
    n = len(closes)
    if n < period + 1:
        return [np.nan] * n
    
    # Calculate +DM, -DM
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    
    for i in range(1, n):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        
        if up_move > down_move and up_move > 0:
            plus_dm[i] = up_move
        if down_move > up_move and down_move > 0:
            minus_dm[i] = down_move
    
    # Calculate ATR for TR smoothing
    atr = calculate_atr(highs, lows, closes, period)
    
    # Smooth +DM and -DM with Wilder's
    smooth_plus_dm = [np.nan] * n
    smooth_minus_dm = [np.nan] * n
    
    if n >= period:
        smooth_plus_dm[period - 1] = sum(plus_dm[:period])
        smooth_minus_dm[period - 1] = sum(minus_dm[:period])
        
        for i in range(period, n):
            smooth_plus_dm[i] = smooth_plus_dm[i - 1] - (smooth_plus_dm[i - 1] / period) + plus_dm[i]
            smooth_minus_dm[i] = smooth_minus_dm[i - 1] - (smooth_minus_dm[i - 1] / period) + minus_dm[i]
    
    # Calculate +DI, -DI
    plus_di = [np.nan] * n
    minus_di = [np.nan] * n
    
    for i in range(n):
        if not np.isnan(smooth_plus_dm[i]) and not np.isnan(atr[i]) and atr[i] > 0:
            plus_di[i] = (smooth_plus_dm[i] / atr[i]) * 100
            minus_di[i] = (smooth_minus_dm[i] / atr[i]) * 100
    
    # Calculate DX
    dx = [np.nan] * n
    for i in range(n):
        if not np.isnan(plus_di[i]) and not np.isnan(minus_di[i]):
            di_sum = plus_di[i] + minus_di[i]
            if di_sum > 0:
                dx[i] = abs(plus_di[i] - minus_di[i]) / di_sum * 100
    
    # Smooth DX to get ADX
    adx = [np.nan] * n
    valid_dx = [i for i in range(n) if not np.isnan(dx[i])]
    
    if len(valid_dx) >= period:
        first_adx_idx = valid_dx[period - 1]
        adx[first_adx_idx] = np.mean([dx[valid_dx[j]] for j in range(period)])
        
        for i in range(first_adx_idx + 1, n):
            if not np.isnan(dx[i]) and not np.isnan(adx[i - 1]):
                adx[i] = (adx[i - 1] * (period - 1) + dx[i]) / period
    
    return adx


def analyze_stock(symbol: str) -> Dict[str, Any]:
    """
    Analyze a stock and return signal based on YESTERDAY's close.
    
    At 9:15 AM, we analyze the completed daily bars (yesterday = last bar).
    We check if yesterday had a TEMA/LSMA crossover.
    """
    candles = get_daily_candles(symbol, days=150)
    
    if len(candles) < LSMA_PERIOD + 5:
        return {"action": None, "reason": "Insufficient data", "data": {}}
    
    # Extract OHLC
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    closes = [c["close"] for c in candles]
    
    # Calculate indicators
    tema = calculate_tema(closes, TEMA_PERIOD)
    lsma = calculate_lsma(closes, LSMA_PERIOD)
    atr = calculate_atr(highs, lows, closes, ATR_PERIOD)
    adx = calculate_adx(highs, lows, closes, ADX_PERIOD)
    
    # Get last two valid bars (yesterday and day before)
    n = len(closes)
    idx_yesterday = n - 1
    idx_prev = n - 2
    
    # Get indicator values
    tema_yesterday = tema[idx_yesterday]
    tema_prev = tema[idx_prev]
    lsma_yesterday = lsma[idx_yesterday]
    lsma_prev = lsma[idx_prev]
    atr_yesterday = atr[idx_yesterday]
    adx_yesterday = adx[idx_yesterday]
    close_yesterday = closes[idx_yesterday]
    
    # Check for valid indicators
    if any(np.isnan(v) for v in [tema_yesterday, tema_prev, lsma_yesterday, lsma_prev]):
        return {"action": None, "reason": "Invalid indicator values", "data": {}}
    
    # Detect crossovers
    bull_cross = (tema_prev <= lsma_prev) and (tema_yesterday > lsma_yesterday)
    bear_cross = (tema_prev >= lsma_prev) and (tema_yesterday < lsma_yesterday)
    is_above = tema_yesterday > lsma_yesterday
    
    # Calculate ATR%
    atr_pct = 0.0
    if not np.isnan(atr_yesterday) and close_yesterday > 0:
        atr_pct = (atr_yesterday / close_yesterday) * 100
    
    # Prepare metadata
    data = {
        "close": close_yesterday,
        "tema": tema_yesterday,
        "lsma": lsma_yesterday,
        "atr_pct": atr_pct,
        "adx": adx_yesterday if not np.isnan(adx_yesterday) else 0,
        "position": "ABOVE" if is_above else "BELOW",
        "cross": "BULL" if bull_cross else ("BEAR" if bear_cross else None),
    }
    
    # ========== EXIT SIGNAL (TEMA crossed below LSMA) ==========
    if bear_cross:
        return {
            "action": "SELL",
            "reason": f"TEMA crossed below LSMA",
            "data": data,
        }
    
    # ========== ENTRY SIGNAL (TEMA crossed above LSMA + filters) ==========
    if bull_cross:
        # Check ATR% filter
        if atr_pct < ATR_PCT_MIN:
            return {
                "action": None,
                "reason": f"ATR% filter blocked: {atr_pct:.2f}% < {ATR_PCT_MIN}%",
                "data": data,
            }
        
        # Check ADX filter
        if np.isnan(adx_yesterday) or adx_yesterday < ADX_MIN:
            adx_val = adx_yesterday if not np.isnan(adx_yesterday) else 0
            return {
                "action": None,
                "reason": f"ADX filter blocked: ADX={adx_val:.1f} < {ADX_MIN}",
                "data": data,
            }
        
        # All filters passed
        return {
            "action": "BUY",
            "reason": f"TEMA crossed above LSMA | ATR%={atr_pct:.2f}% | ADX={adx_yesterday:.1f}",
            "data": data,
        }
    
    # No crossover - check current state
    if is_above:
        return {"action": "HOLD", "reason": "TEMA above LSMA, holding", "data": data}
    else:
        return {"action": None, "reason": "TEMA below LSMA, no position", "data": data}


# ═══════════════════════════════════════════════════════════════════════════════
# TIME CHECK
# ═══════════════════════════════════════════════════════════════════════════════

now = datetime.now()
h, m = now.hour, now.minute

# Entry window: 9:15-9:30 AM (avoid 9:15 auction volatility, process yesterday's signals)
is_entry_window = h == 9 and 15 <= m <= 30

# Full market hours: 9:15 AM - 3:30 PM
# Process entries 9:15-9:30, exits throughout the day
is_market = (h == 9 and m >= 15) or (10 <= h <= 14) or (h == 15 and m <= 30)

print(f"\n⏰ {now.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"   Entry Window: {is_entry_window} | Full Market Hours: {is_market}")

if not is_market:
    print("⛔ Outside market hours (9:15 AM - 3:30 PM), exiting")
    raise SystemExit(0)

if not is_entry_window:
    print("⏸️ Outside entry window (9:15-9:30 AM), exiting")
    print("   This strategy runs daily at 9:15-9:30 AM to process yesterday's signals")
    print("   Exits are processed during this window; hold positions are managed throughout the day")
    raise SystemExit(0)

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
    for sym, h in list(strategy_holdings.items())[:10]:
        ltp = get_ltp(sym)
        entry = tracked.get(sym, {}).get("entry", h["avg"])
        pnl = ((ltp - entry) / entry * 100) if entry > 0 and ltp > 0 else 0
        print(f"      {sym}: {h['qty']} @ ₹{entry:.2f} → ₹{ltp:.2f} ({pnl:+.2f}%)")
        time.sleep(0.05)
    if len(strategy_holdings) > 10:
        print(f"      ... and {len(strategy_holdings) - 10} more")

# ═══════════════════════════════════════════════════════════════════════════════
# PROCESS EXITS (TEMA crossed below LSMA)
# ═══════════════════════════════════════════════════════════════════════════════

print(f"\n📤 Processing exits for {len(strategy_holdings)} positions...")
exits = 0
exit_log = []

for sym, holding in strategy_holdings.items():
    time.sleep(0.15)  # Rate limiting
    signal = analyze_stock(sym)
    
    if signal["action"] == "SELL":
        try:
            ltp = get_ltp(sym)
            entry = tracked.get(sym, {}).get("entry", holding["avg"])
            pnl = ((ltp - entry) / entry * 100) if entry > 0 and ltp > 0 else 0
            
            # Use limit order for better fill (0.5% below current price for sell)
            order = place_order(sym, holding["qty"], groww.TRANSACTION_TYPE_SELL, price=ltp, is_limit=True)
            oid = order.get("groww_order_id", "N/A")
            status = order.get("order_status", "UNKNOWN")
            
            # Track actual fill price (order_filled_price) or fallback to LTP
            fill_price = order.get("order_filled_price", ltp)
            if not fill_price or fill_price <= 0:
                fill_price = ltp
            
            # Recalculate P&L using actual fill price
            pnl = ((fill_price - entry) / entry * 100) if entry > 0 and fill_price > 0 else 0
            
            print(f"   ✅ SELL {sym}: {holding['qty']} @ ₹{fill_price:.2f} | P&L: {pnl:+.2f}% | {signal['reason']} [{oid}:{status}]")
            
            exit_log.append({
                "symbol": sym,
                "qty": holding["qty"],
                "entry": entry,
                "exit": fill_price,  # Use actual fill price, not LTP
                "pnl_pct": pnl,
                "reason": signal["reason"],
                "order_id": oid,
                "status": status,
                "timestamp": datetime.now().isoformat(),
            })
            
            # Remove from tracked positions
            if sym in tracked:
                del tracked[sym]
            
            exits += 1
            
        except Exception as e:
            print(f"   ❌ SELL {sym} failed: {e}")

print(f"   Exits processed: {exits}")

# ═══════════════════════════════════════════════════════════════════════════════
# PROCESS ENTRIES (TEMA crossed above LSMA + filters)
# ═══════════════════════════════════════════════════════════════════════════════

current_positions = len(strategy_holdings) - exits
available_slots = MAX_POSITIONS - current_positions

print(f"\n📥 Processing entries (Available slots: {available_slots})...")
entries = 0
entry_log = []

if available_slots <= 0:
    print("   ⚠️ Max positions reached, skipping entries")
else:
    # Scan symbols not in current holdings
    symbols_to_scan = [s for s in SYMBOLS if s not in strategy_holdings]
    print(f"   Scanning {len(symbols_to_scan)} symbols...")
    
    for sym in symbols_to_scan:
        if entries >= available_slots:
            print(f"   ⚠️ Max positions reached ({MAX_POSITIONS}), stopping")
            break
        
        time.sleep(0.15)  # Rate limiting
        signal = analyze_stock(sym)
        
        if signal["action"] == "BUY":
            try:
                ltp = get_ltp(sym)
                if ltp <= 0:
                    print(f"   ⚠️ {sym}: Could not get LTP, skipping")
                    continue
                
                qty = calc_qty(ltp)
                if qty <= 0:
                    print(f"   ⚠️ {sym}: Price too high (₹{ltp:.2f}), skipping")
                    continue
                
                # Use limit order for better fill (0.5% above current price for buy)
                order = place_order(sym, qty, groww.TRANSACTION_TYPE_BUY, price=ltp, is_limit=True)
                oid = order.get("groww_order_id", "N/A")
                status = order.get("order_status", "UNKNOWN")
                
                # Track actual fill price (order_filled_price) or fallback to LTP
                fill_price = order.get("order_filled_price", ltp)
                if not fill_price or fill_price <= 0:
                    fill_price = ltp
                
                print(f"   ✅ BUY {sym}: {qty} @ ₹{fill_price:.2f} | {signal['reason']} [{oid}:{status}]")
                
                # Track position with actual fill price (not LTP at order time)
                tracked[sym] = {
                    "entry": fill_price,  # Use actual fill price for accurate P&L
                    "qty": qty,
                    "entry_time": datetime.now().isoformat(),
                    "reason": signal["reason"],
                    "order_id": oid,
                }
                
                entry_log.append({
                    "symbol": sym,
                    "qty": qty,
                    "price": fill_price,  # Use actual fill price
                    "reason": signal["reason"],
                    "order_id": oid,
                    "status": status,
                    "timestamp": datetime.now().isoformat(),
                })
                
                entries += 1
                
            except Exception as e:
                print(f"   ❌ BUY {sym} failed: {e}")

print(f"   Entries processed: {entries}")

# ═══════════════════════════════════════════════════════════════════════════════
# SAVE STATE
# ═══════════════════════════════════════════════════════════════════════════════

print("\n💾 Saving state...")
save_json(POSITIONS_FILE, tracked)

# Append to daily log
daily_log = load_json(SIGNALS_LOG_FILE, {"entries": [], "exits": []})
daily_log["entries"].extend(entry_log)
daily_log["exits"].extend(exit_log)
save_json(SIGNALS_LOG_FILE, daily_log)

# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("📊 TEMA-LSMA CROSSOVER - SESSION SUMMARY")
print("=" * 60)
print(f"   Strategy: TEMA({TEMA_PERIOD})/LSMA({LSMA_PERIOD}) Crossover")
print(f"   Filters: ATR({ATR_PERIOD})% > {ATR_PCT_MIN}%, ADX({ADX_PERIOD}) > {ADX_MIN}")
print(f"   Entries: {entries}")
print(f"   Exits: {exits}")
print(f"   Active Positions: {current_positions + entries}")
print("=" * 60)
