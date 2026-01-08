"""
Weekly Green BB Strategy - CNC (Delivery)
==========================================

Groww Cloud Schedule:
    - First trading day of week 9:15-9:30 AM: Check for new entry signals
    - Daily 9:15-9:30 AM + 3:00-3:30 PM: Check TP (EMA touch) + SL
    
    Note: TP check happens at scheduled times only. Intraday price may touch
    EMA between checks causing slippage. For tighter exits, increase check
    frequency or use bracket orders if supported.

Strategy (Mean Reversion):
    Entry Conditions (first trading day after signal week):
        1. Previous week candle was GREEN (close > open)
        2. Previous week OPEN was below BB lower band (SMA 20 ± 2 SD)
        3. Previous week body size > week before that
        4. Weekly RSI(14) < 60 on signal week
    
    Exit Conditions:
        - TP: Daily HIGH touches Weekly SMA(20)
        - SL: 30% fixed stop loss from entry price
    
    Product: CNC (delivery, held in DEMAT)

Backtest Results (Main Basket - 563 symbols):
    1Y:  +36.15%, 83% WR, 154 trades, PF 6.36
    3Y:  +42.67%, 79% WR, 248 trades, PF 3.48
    5Y:  +69.69%, 79% WR, 428 trades, PF 3.16
    MAX: +226.05%, 77% WR, 906 trades, PF 3.66
"""

import json
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import pyotp
from growwapi import GrowwAPI

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION (TOTP Flow - No daily expiry, expires 2055)
# ═══════════════════════════════════════════════════════════════════════════════

GROWW_TOTP_TOKEN = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTUxNjc3NDAsImlhdCI6MTc2Njc2Nzc0MCwibmJmIjoxNzY2NzY3NzQwLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJmYTVjOWUwZi02OGQ1LTRmYWItOTcwZi0zNjRiNTE3ZDk1ZDlcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiM2IzY2M4NTktYWYzNS00MWY3LWI0OTgtYmM2ODFlNDRjYzg3XCIsXCJkZXZpY2VJZFwiOlwiMTA1MDU5YzctNzFlOC01ZjNlLWI2MDctZGNjYzc4MGJjNWU4XCIsXCJzZXNzaW9uSWRcIjpcIjQ0ZTAzY2MwLWZlN2QtNDcxYy1iYjNlLTYwZDdiYzg3NDkyNVwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1seHBMN0FMeEhDTkRWT1YycnBuUzlSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIxNC4xMDIuMTYzLjExNiwxNzIuNzAuMjE4LjE4OCwzNS4yNDEuMjMuMTIzXCIsXCJ0d29GYUV4cGlyeVRzXCI6MjU1NTE2Nzc0MDIwMH0iLCJpc3MiOiJhcGV4LWF1dGgtcHJvZC1hcHAifQ.CVtkRiVV5KoFcDQiANb6TUIft8tufL8nBsmyNuth61cxPzXHEodcpCGs_AT0qLwk5Cabo1u-ki1SDJjBOV6_pA"
GROWW_TOTP_SECRET = "JVG42CV6PHCLMTVNSTKEQPN7AOAAL43F"

# Strategy parameters
INITIAL_CAPITAL = 100000
POSITION_SIZE_PCT = 0.10  # 10% per position
MAX_POSITIONS = 5
STOP_PCT = 0.30  # 30% stop loss
BB_PERIOD = 20  # SMA period for BB center line
BB_SD = 2.0
SMA_PERIOD = 20  # Same as BB_PERIOD - TP target is SMA(20)
RSI_PERIOD = 14
RSI_MAX = 60  # Weekly RSI must be below this
API_RETRY_DELAY = 0.2  # Delay between API calls
API_MAX_RETRIES = 3  # Max retries for data endpoints

# Files - Use home directory for persistence
HOME_DIR = os.path.expanduser("~")
if HOME_DIR == "/" or not HOME_DIR:
    HOME_DIR = "/tmp"
POSITIONS_FILE = os.path.join(HOME_DIR, ".groww_weekly_green_bb_positions.json")
SIGNALS_FILE = os.path.join(HOME_DIR, ".groww_weekly_green_bb_signals.json")

# Main Basket - 563 symbols
SYMBOLS = [
    "360ONE", "3MINDIA", "AADHARHFC", "AARTIIND", "AAVAS", "ABB", "ABBOTINDIA",
    "ABCAPITAL", "ABDL", "ABFRL", "ABLBL", "ABSLAMC", "ACC", "ACE", "ACMESOLAR",
    "ACUTAAS", "ADANIENSOL", "ADANIENT", "ADANIGREEN", "ADANIPORTS", "ADANIPOWER",
    "AEGISLOG", "AEGISVOPAK", "AETHER", "AFCONS", "AFFLE", "AGARWALEYE", "AIAENG",
    "AIIL", "AJANTPHARM", "AKZOINDIA", "ALIVUS", "ALKEM", "ALKYLAMINE", "ALOKINDS",
    "AMBER", "AMBUJACEM", "ANANDRATHI", "ANANTRAJ", "ANGELONE", "ANTHEM", "ANURAS",
    "APARINDS", "APLAPOLLO", "APLLTD", "APOLLO", "APOLLOHOSP", "APOLLOTYRE", "APTUS",
    "ARE&M", "ARVIND", "ASAHIINDIA", "ASHOKLEY", "ASIANPAINT", "ASKAUTOLTD", "ASTERDM",
    "ASTRAL", "ASTRAMICRO", "ASTRAZEN", "ATGL", "ATHERENERG", "ATUL", "AUBANK",
    "AUROPHARMA", "AVANTIFEED", "AWL", "AXISBANK", "AZAD", "BAJAJ-AUTO", "BAJAJFINSV",
    "BAJAJHFL", "BAJAJHLDNG", "BAJFINANCE", "BALKRISIND", "BALRAMCHIN", "BANCOINDIA",
    "BANDHANBNK", "BANKBARODA", "BANKINDIA", "BASF", "BATAINDIA", "BAYERCROP", "BBOX",
    "BBTC", "BDL", "BEL", "BELRISE", "BEML", "BERGEPAINT", "BHARATFORG", "BHARTIARTL",
    "BHARTIHEXA", "BHEL", "BIKAJI", "BIOCON", "BIRLACORPN", "BLACKBUCK", "BLS",
    "BLUEDART", "BLUEJET", "BLUESTARCO", "BORORENEW", "BOSCHLTD", "BPCL", "BRIGADE",
    "BRITANNIA", "BSE", "BSOFT", "CAMS", "CANFINHOME", "CAPLIPOINT", "CARBORUNIV",
    "CARTRADE", "CASTROLIND", "CCL", "CDSL", "CEATLTD", "CELLO", "CEMPRO", "CENTRALBK",
    "CENTURYPLY", "CESC", "CGCL", "CGPOWER", "CHALET", "CHAMBLFERT", "CHENNPETRO",
    "CHOICEIN", "CHOLAFIN", "CHOLAHLDNG", "CIPLA", "CLEAN", "COALINDIA", "COCHINSHIP",
    "COFORGE", "COLPAL", "CONCOR", "CONCORDBIO", "COROMANDEL", "CRAFTSMAN", "CREDITACC",
    "CRISIL", "CROMPTON", "CUB", "CUMMINSIND", "CYIENT", "DABUR", "DALBHARAT",
    "DATAPATTNS", "DCMSHRIRAM", "DEEPAKFERT", "DEEPAKNTR", "DELHIVERY", "DEVYANI",
    "DIVISLAB", "DIXON", "DLF", "DMART", "DOMS", "DRREDDY", "ECLERX", "EDELWEISS",
    "EICHERMOT", "EIDPARRY", "EIHOTEL", "ELECON", "ELGIEQUIP", "EMAMILTD", "EMCURE",
    "ENDURANCE", "ENGINERSIN", "ENRIN", "ERIS", "ESCORTS", "ETERNAL", "EUREKAFORB",
    "EXIDEIND", "FACT", "FEDERALBNK", "FINCABLES", "FINEORG", "FINPIPE", "FIRSTCRY",
    "FIVESTAR", "FLUOROCHEM", "FORCEMOT", "FORTIS", "FSL", "GABRIEL", "GAIL",
    "GALLANTT", "GENUSPOWER", "GESHIP", "GICRE", "GILLETTE", "GLAND", "GLAXO",
    "GLENMARK", "GMDCLTD", "GMRAIRPORT", "GMRP&UI", "GODFRYPHLP", "GODIGIT",
    "GODREJAGRO", "GODREJCP", "GODREJIND", "GODREJPROP", "GPIL", "GPPL", "GRANULES",
    "GRAPHITE", "GRASIM", "GRAVITA", "GRINDWELL", "GRINFRA", "GRSE", "GSPL",
    "GUJGASLTD", "GVT&D", "HAL", "HAPPYFORGE", "HATSUN", "HAVELLS", "HBLENGINE",
    "HCG", "HCLTECH", "HDBFS", "HDFCAMC", "HDFCBANK", "HDFCLIFE", "HEG", "HEROMOTOCO",
    "HEXT", "HFCL", "HINDALCO", "HINDCOPPER", "HINDUNILVR", "HINDZINC", "HOMEFIRST",
    "HONASA", "HONAUT", "HSCL", "HUDCO", "HYUNDAI", "ICICIBANK", "ICICIPRULI", "IDBI",
    "IDFCFIRSTB", "IEX", "IFCI", "IGIL", "IGL", "IIFL", "IIFLCAPS", "IKS", "INDGN",
    "INDHOTEL", "INDIACEM", "INDIAMART", "INDIANB", "INDIASHLTR", "INDIGO",
    "INDUSINDBK", "INDUSTOWER", "INFY", "INGERRAND", "INOXGREEN", "INOXINDIA",
    "INOXWIND", "INTELLECT", "IOB", "IOC", "IPCALAB", "IRB", "IRCON", "IRCTC", "IREDA",
    "IRFC", "ITC", "ITCHOTELS", "ITI", "IXIGO", "J&KBANK", "JBCHEPHARM", "JBMA",
    "JINDALSAW", "JINDALSTEL", "JIOFIN", "JKCEMENT", "JKLAKSHMI", "JKTYRE", "JLHL",
    "JMFINANCIL", "JPPOWER", "JSL", "JSWENERGY", "JSWHL", "JSWINFRA", "JSWSTEEL",
    "JUBLFOOD", "JUBLINGREA", "JUBLPHARMA", "JWL", "JYOTHYLAB", "JYOTICNC",
    "KAJARIACER", "KALYANKJIL", "KANSAINER", "KARURVYSYA", "KAYNES", "KEC", "KEI",
    "KFINTECH", "KIMS", "KIOCL", "KIRLOSBROS", "KIRLOSENG", "KOTAKBANK", "KPIGREEN",
    "KPIL", "KPITTECH", "KPRMILL", "KRBL", "KSB", "LALPATHLAB", "LATENTVIEW",
    "LAURUSLABS", "LEMONTREE", "LICHSGFIN", "LICI", "LINDEINDIA", "LLOYDSENT",
    "LLOYDSME", "LMW", "LODHA", "LT", "LTFOODS", "LTIM", "LTTS", "LUPIN", "M&M",
    "M&MFIN", "MAHABANK", "MANAPPURAM", "MANKIND", "MANYAVAR", "MAPMYINDIA", "MARICO",
    "MARUTI", "MAXHEALTH", "MAZDOCK", "MCX", "MEDANTA", "MEDPLUS", "METROBRAND",
    "METROPOLIS", "MFSL", "MGL", "MINDACORP", "MMTC", "MOTILALOFS", "MPHASIS", "MRF",
    "MRPL", "MSUMI", "MUTHOOTFIN", "NATCOPHARM", "NATIONALUM", "NAUKRI", "NAVA",
    "NAVINFLUOR", "NAZARA", "NBCC", "NCC", "NESCO", "NESTLEIND", "NETWEB", "NEULANDLAB",
    "NEWGEN", "NH", "NHPC", "NIACL", "NIVABUPA", "NLCINDIA", "NMDC", "NSLNISP", "NTPC",
    "NTPCGREEN", "NUVAMA", "NUVOCO", "NYKAA", "OBEROIRLTY", "OFSS", "OIL", "OLAELEC",
    "OLECTRA", "ONESOURCE", "ONGC", "PAGEIND", "PARADEEP", "PAYTM", "PCBL",
    "PERSISTENT", "PETRONET", "PFC", "PFIZER", "PGEL", "PGHH", "PGHL", "PGINVIT",
    "PHOENIXLTD", "PIDILITIND", "PIIND", "PNB", "PNBHOUSING", "PNGJL", "POLICYBZR",
    "POLYCAB", "POLYMED", "POWERGRID", "POWERINDIA", "PPLPHARMA", "PREMIERENE",
    "PRESTIGE", "PRIVISCL", "PRUDENT", "PSB", "PTCIL", "RADICO", "RAILTEL", "RAINBOW",
    "RAMCOCEM", "RATNAMANI", "RBLBANK", "RECLTD", "REDINGTON", "RELAXO", "RELIANCE",
    "RELIGARE", "RHIM", "RITES", "RKFORGE", "RPOWER", "RRKABEL", "RVNL", "SAFARI",
    "SAGILITY", "SAIL", "SAILIFE", "SANDUMA", "SANOFI", "SANOFICONR", "SANSERA",
    "SAPPHIRE", "SARDAEN", "SBFC", "SBICARD", "SBILIFE", "SBIN", "SCHAEFFLER",
    "SCHNEIDER", "SCI", "SHAILY", "SHAKTIPUMP", "SHREECEM", "SHRIPISTON", "SHRIRAMFIN",
    "SHYAMMETL", "SIEMENS", "SIGNATURE", "SJVN", "SOBHA", "SOLARINDS", "SONACOMS",
    "SONATSOFTW", "SPLPETRO", "SRF", "STAR", "STARCEMENT", "STARHEALTH", "SUMICHEM",
    "SUNDARMFIN", "SUNDRMFAST", "SUNPHARMA", "SUNTV", "SUPREMEIND", "SUZLON",
    "SWANCORP", "SWIGGY", "SYNGENE", "SYRMA", "TARIL", "TATACHEM", "TATACOMM",
    "TATACONSUM", "TATAELXSI", "TATAINVEST", "TATAPOWER", "TATASTEEL", "TATATECH",
    "TBOTEK", "TCI", "TCS", "TDPOWERSYS", "TECHM", "TECHNOE", "TEGA", "TEJASNET",
    "THANGAMAYL", "THELEELA", "THERMAX", "TI", "TIINDIA", "TIMETECHNO", "TIMKEN",
    "TITAGARH", "TITAN", "TMPV", "TORNTPHARM", "TORNTPOWER", "TRANSRAILL", "TRAVELFOOD",
    "TRENT", "TRIDENT", "TRITURBINE", "TTKPRESTIG", "TTML", "TVSMOTOR", "UBL",
    "UCOBANK", "UJJIVANSFB", "ULTRACEMCO", "UNIONBANK", "UNITDSPR", "UNOMINDA", "UPL",
    "USHAMART", "UTIAMC", "VARROC", "VBL", "VEDL", "VENTIVE", "VESUVIUS", "VGUARD",
    "VIJAYA", "VINATIORGA", "VMM", "VOLTAS", "VTL", "WAAREEENER", "WAAREERTL", "WABAG",
    "WELCORP", "WELSPUNLIV", "WESTLIFE", "WHIRLPOOL", "WIPRO", "WOCKPHARMA",
    "ZENSARTECH", "ZENTEC", "ZFCVINDIA", "ZYDUSLIFE", "ZYDUSWELL",
]

# ═══════════════════════════════════════════════════════════════════════════════
# INITIALIZE API (TOTP Flow with Retry)
# ═══════════════════════════════════════════════════════════════════════════════

RETRYABLE_ERRORS = {
    'GA000': 'Internal error occurred',
    'GA003': 'Unable to serve request currently',
}


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
    
    # Groww API error codes (GA000, GA003)
    if any(code in error_msg for code in RETRYABLE_ERRORS):
        return True
    
    # Check for actual error messages (not just codes)
    retryable_messages = ['internal error', 'unable to serve', 'service unavailable', 'try again']
    if any(x in error_lower for x in retryable_messages):
        return True
    
    # Default: retry unknown errors once
    return True


def init_groww_api(max_retries: int = 3, retry_delay: int = 5) -> GrowwAPI:
    """Initialize Groww API with retry logic."""
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

def api_call_with_retry(func, *args, max_retries: int = API_MAX_RETRIES, **kwargs):
    """Wrapper to retry API calls on transient errors."""
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_error = e
            error_msg = str(e)
            if is_retryable_error(error_msg) and attempt < max_retries:
                wait_time = API_RETRY_DELAY * attempt * 2
                time.sleep(wait_time)
            else:
                break
    raise last_error


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
    """Save data to JSON file."""
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except Exception as e:
        print(f"   ⚠️ Error saving {path}: {e}")
        return False


def get_ltp(symbol: str) -> float:
    """Get last traded price. Returns 0 on failure."""
    try:
        resp = api_call_with_retry(
            groww.get_ltp,
            segment=groww.SEGMENT_CASH,
            exchange_trading_symbols=f"NSE_{symbol}",
        )
        price = resp.get(f"NSE_{symbol}", 0)
        return float(price) if price else 0.0
    except Exception as e:
        print(f"   ⚠️ LTP error for {symbol}: {e}")
        return 0.0


def get_ohlc(symbol: str) -> Dict[str, float]:
    """Get today's OHLC."""
    try:
        resp = api_call_with_retry(
            groww.get_ohlc,
            segment=groww.SEGMENT_CASH,
            exchange_trading_symbols=f"NSE_{symbol}",
        )
        ohlc_raw = resp.get(f"NSE_{symbol}", {})
        
        if isinstance(ohlc_raw, dict):
            return {
                "open": float(ohlc_raw.get("open", 0) or 0),
                "high": float(ohlc_raw.get("high", 0) or 0),
                "low": float(ohlc_raw.get("low", 0) or 0),
                "close": float(ohlc_raw.get("close", 0) or 0),
            }
        return {}
    except Exception as e:
        print(f"   ⚠️ OHLC error for {symbol}: {e}")
        return {}


def get_weekly_candles(symbol: str, weeks: int = 25) -> List[Dict]:
    """
    Get weekly candles for a symbol.
    Returns list of {open, high, low, close, volume, timestamp} dicts.
    Only returns completed weeks (filters out current incomplete week).
    
    Note: Groww API limits 1week interval to 180 days max.
    """
    try:
        end = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # API limit: 1week candles max 180 days (approx 25 weeks)
        max_days = min(weeks * 7, 175)  # Stay under 180 day limit
        start = (datetime.now() - timedelta(days=max_days)).strftime("%Y-%m-%d %H:%M:%S")
        
        resp = api_call_with_retry(
            groww.get_historical_candles,
            exchange=groww.EXCHANGE_NSE,
            segment=groww.SEGMENT_CASH,
            groww_symbol=f"NSE-{symbol}",
            start_time=start,
            end_time=end,
            candle_interval=groww.CANDLE_INTERVAL_WEEK,
        )
        
        candles = resp.get("candles", []) if resp else []
        
        result = []
        for c in candles:
            if c and len(c) >= 5:
                try:
                    result.append({
                        "timestamp": c[0],
                        "open": float(c[1]),
                        "high": float(c[2]),
                        "low": float(c[3]),
                        "close": float(c[4]),
                        "volume": float(c[5]) if len(c) > 5 else 0,
                    })
                except (ValueError, TypeError):
                    continue
        
        # Filter out current incomplete week by checking timestamp
        # Week is complete if its start is before current week start
        if result:
            now = datetime.now()
            # Current week starts on Monday 00:00
            days_since_monday = now.weekday()
            current_week_start = (now - timedelta(days=days_since_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            
            # Parse last candle timestamp and check if it's current week
            try:
                last_ts = result[-1]["timestamp"]
                if isinstance(last_ts, str):
                    # Try common formats
                    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
                        try:
                            last_dt = datetime.strptime(last_ts[:19], fmt)
                            break
                        except ValueError:
                            continue
                    else:
                        last_dt = None
                elif isinstance(last_ts, (int, float)):
                    last_dt = datetime.fromtimestamp(last_ts)
                else:
                    last_dt = None
                
                # If last candle is from current week, it's incomplete - remove it
                if last_dt and last_dt >= current_week_start:
                    result = result[:-1]
            except Exception:
                pass  # Keep all candles if we can't parse
        
        return result
    except Exception as e:
        print(f"   ⚠️ Weekly candles error for {symbol}: {e}")
        return []


def calculate_bb_lower(candles: List[Dict], period: int = 20, sd: float = 2.0) -> Optional[float]:
    """
    Calculate Bollinger Band lower value from weekly candles.
    Uses SMA as center line with sample std (ddof=1) to match TradingView.
    """
    if len(candles) < period:
        return None
    
    closes = pd.Series([c["close"] for c in candles])
    sma = closes.rolling(period).mean().iloc[-1]
    # Use sample std (ddof=1) to match TradingView ta.stdev()
    std = np.std([c["close"] for c in candles[-period:]], ddof=1)
    return sma - sd * std


def calculate_weekly_sma(candles: List[Dict], period: int = 20) -> Optional[float]:
    """Calculate SMA from weekly candles (TP target)."""
    if len(candles) < period:
        return None
    
    closes = pd.Series([c["close"] for c in candles])
    sma = closes.rolling(period).mean()
    return sma.iloc[-1]


def calculate_weekly_rsi(candles: List[Dict], period: int = 14) -> Optional[float]:
    """Calculate RSI from weekly candles."""
    if len(candles) < period + 1:
        return None
    
    closes = pd.Series([c["close"] for c in candles])
    delta = closes.diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    
    avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean()
    
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    
    return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else None


def check_signal(symbol: str) -> Optional[Dict]:
    """
    Check if symbol has a valid entry signal.
    
    Signal Conditions:
    1. Last completed week is GREEN (close > open)
    2. Last week's OPEN is below BB lower band (EMA - 2*SD)
    3. Last week's body > previous week's body
    4. Weekly RSI < 60
    
    Returns signal dict with entry info, or None.
    """
    candles = get_weekly_candles(symbol, weeks=30)
    
    # get_weekly_candles now returns only completed weeks
    if len(candles) < BB_PERIOD + 2:
        return None
    
    # Last two completed weeks
    last_week = candles[-1]
    prev_week = candles[-2]
    
    # Calculate indicators using all completed candles
    bb_lower = calculate_bb_lower(candles, BB_PERIOD, BB_SD)
    weekly_sma = calculate_weekly_sma(candles, SMA_PERIOD)
    weekly_rsi = calculate_weekly_rsi(candles, RSI_PERIOD)
    
    if bb_lower is None or weekly_sma is None or weekly_rsi is None:
        return None
    
    # Check conditions
    is_green = last_week["close"] > last_week["open"]
    opens_below_bb = last_week["open"] < bb_lower
    last_body = abs(last_week["close"] - last_week["open"])
    prev_body = abs(prev_week["close"] - prev_week["open"])
    bigger_body = last_body > prev_body
    rsi_ok = weekly_rsi < RSI_MAX
    
    if is_green and opens_below_bb and bigger_body and rsi_ok:
        return {
            "symbol": symbol,
            "bb_lower": bb_lower,
            "weekly_sma": weekly_sma,
            "weekly_rsi": weekly_rsi,
            "last_close": last_week["close"],
            "last_open": last_week["open"],
            "signal_date": last_week["timestamp"],
        }
    
    return None


def get_holdings() -> Dict[str, Dict]:
    """Get CNC holdings."""
    try:
        resp = api_call_with_retry(groww.get_holdings_for_user)
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


def get_order_details(order_id: str) -> Optional[Dict]:
    """Get order details to fetch executed price."""
    try:
        resp = api_call_with_retry(groww.get_order_by_id, order_id=order_id)
        if resp:
            return {
                "status": resp.get("order_status"),
                "avg_price": float(resp.get("average_price", 0) or 0),
                "filled_qty": int(float(resp.get("filled_quantity", 0) or 0)),
            }
    except Exception as e:
        print(f"   ⚠️ Order details error: {e}")
    return None


def place_order(symbol: str, qty: int, txn_type: str) -> Dict:
    """Place CNC order."""
    return api_call_with_retry(
        groww.place_order,
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

# First trading day of week logic:
# - Monday (weekday=0) is default entry day
# - If Monday is holiday (no OHLC data), Tuesday becomes entry day, etc.
# - We track "already_entered_this_week" in signals file to avoid duplicate entries
is_early_week = now.weekday() in [0, 1, 2]  # Mon, Tue, Wed - potential entry days
is_entry_window = h == 9 and 15 <= m <= 30
is_exit_window = (h == 9 and 15 <= m <= 30) or (h == 15 and 0 <= m <= 30)
is_market = (h == 9 and m >= 15) or (10 <= h <= 14) or (h == 15 and m <= 30)

# Track week number to detect first trading day
current_week = now.isocalendar()[1]
signals_state = load_json(SIGNALS_FILE, {"last_entry_week": 0})
already_entered_this_week = signals_state.get("last_entry_week", 0) == current_week

print(f"\n📅 {now.strftime('%A %Y-%m-%d %H:%M:%S')}")
print(f"   Early Week: {is_early_week} | Entry Window: {is_entry_window} | Exit Window: {is_exit_window}")
print(f"   Week #{current_week} | Already Entered: {already_entered_this_week}")

if not is_market:
    print("⛔ Outside market hours")
    raise SystemExit(0)


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1: CHECK EXISTING POSITIONS (TP + SL)
# ═══════════════════════════════════════════════════════════════════════════════

print("\n📊 Checking existing positions...")

positions = load_json(POSITIONS_FILE, {})
holdings = get_holdings()
exits = []
positions_to_remove = []

for sym, pos in list(positions.items()):
    if sym not in holdings:
        print(f"   ⚠️ {sym}: Not in holdings, removing from tracking")
        positions_to_remove.append(sym)
        continue
    
    ohlc = get_ohlc(sym)
    ltp = get_ltp(sym) or ohlc.get("close", 0)
    high = ohlc.get("high", ltp) or ltp
    low = ohlc.get("low", ltp) or ltp
    entry = pos.get("entry", 0)
    stop = pos.get("stop", 0)
    weekly_sma = pos.get("weekly_sma", 0)
    pnl = ((ltp - entry) / entry * 100) if entry > 0 else 0
    
    # Check Stop Loss
    if low > 0 and stop > 0 and low <= stop:
        exits.append({
            "sym": sym,
            "qty": holdings[sym]["qty"],
            "ltp": ltp,
            "pnl": pnl,
            "reason": "STOP LOSS",
        })
        print(f"   🛑 {sym}: STOP HIT (low={low:.2f} <= stop={stop:.2f})")
        continue
    
    # Check Take Profit (SMA touch)
    if weekly_sma > 0 and high >= weekly_sma:
        exits.append({
            "sym": sym,
            "qty": holdings[sym]["qty"],
            "ltp": ltp,
            "pnl": pnl,
            "reason": "TP: SMA Touch",
        })
        print(f"   🎯 {sym}: TP HIT (high={high:.2f} >= sma={weekly_sma:.2f})")
        continue
    
    dist_to_stop = ((ltp - stop) / ltp * 100) if ltp > 0 and stop > 0 else 0
    dist_to_sma = ((weekly_sma - ltp) / ltp * 100) if ltp > 0 and weekly_sma > 0 else 0
    print(f"   📊 {sym}: ₹{ltp:.2f} | P&L={pnl:+.2f}% | Stop={dist_to_stop:.1f}% away | SMA={dist_to_sma:.1f}% away")

# Remove stale positions
for sym in positions_to_remove:
    if sym in positions:
        del positions[sym]

save_json(POSITIONS_FILE, positions)

# Execute exits
for e in exits:
    try:
        order = place_order(e["sym"], e["qty"], groww.TRANSACTION_TYPE_SELL)
        oid = order.get("groww_order_id", "N/A")
        print(f"   ✅ {e['sym']}: SELL {e['qty']} @ ₹{e['ltp']:.2f} | P&L: {e['pnl']:+.2f}% | {e['reason']} [{oid}]")
        if e["sym"] in positions:
            del positions[e["sym"]]
    except Exception as ex:
        print(f"   ❌ {e['sym']}: {ex}")
    time.sleep(0.3)

save_json(POSITIONS_FILE, positions)


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2: FIRST TRADING DAY OF WEEK ENTRY LOGIC
# ═══════════════════════════════════════════════════════════════════════════════

if not is_early_week:
    print(f"\n⏸️ {now.strftime('%A')} - Exit check only (entries early in week)")
    print(f"   Active positions: {len(positions)}")
    raise SystemExit(0)

if not is_entry_window:
    print(f"\n⏸️ {now.strftime('%A')} outside entry window (9:15-9:30 AM)")
    print(f"   Active positions: {len(positions)}")
    raise SystemExit(0)

if already_entered_this_week:
    print(f"\n⏸️ Already scanned for entries this week (week #{current_week})")
    print(f"   Active positions: {len(positions)}")
    raise SystemExit(0)

print("\n📈 First Trading Day Entry Window - Scanning for signals...")

# Calculate available slots
holdings = get_holdings()
current_positions = len([s for s in positions if s in holdings])
available_slots = MAX_POSITIONS - current_positions

if available_slots <= 0:
    print(f"   ⚠️ Max positions reached ({MAX_POSITIONS})")
    raise SystemExit(0)

print(f"   Available slots: {available_slots}/{MAX_POSITIONS}")

# Scan for signals
signals = []
scanned = 0

for sym in SYMBOLS:
    # Skip if already in position
    if sym in positions or sym in holdings:
        continue
    
    scanned += 1
    if scanned % 50 == 0:
        print(f"   Scanned {scanned}/{len(SYMBOLS)}...")
    
    signal = check_signal(sym)
    if signal:
        signals.append(signal)
    
    time.sleep(0.15)  # Rate limiting

print(f"\n   Total scanned: {scanned}")
print(f"   Signals found: {len(signals)}")

if signals:
    # Sort by RSI (lower is more oversold)
    signals.sort(key=lambda x: x["weekly_rsi"])
    
    print("\n🎯 Top signals (sorted by RSI):")
    for s in signals[:10]:
        print(f"   {s['symbol']}: RSI={s['weekly_rsi']:.1f}, Close=₹{s['last_close']:.2f}, SMA=₹{s['weekly_sma']:.2f}")

# Place entry orders
print(f"\n💰 Placing CNC orders...")

placed = 0
for signal in signals[:available_slots]:
    sym = signal["symbol"]
    
    # Use today's OPEN as entry price proxy (more accurate than LTP for market orders at open)
    ohlc = get_ohlc(sym)
    entry_price = ohlc.get("open", 0)
    
    if entry_price <= 0:
        # Fallback to LTP if open not available
        entry_price = get_ltp(sym)
    
    if entry_price <= 0:
        print(f"   ⏭️ {sym}: Invalid price")
        continue
    
    qty = calc_qty(entry_price)
    if qty < 1:
        print(f"   ⏭️ {sym}: Qty too low at ₹{entry_price:.2f}")
        continue
    
    stop = entry_price * (1 - STOP_PCT)
    
    try:
        order = place_order(sym, qty, groww.TRANSACTION_TYPE_BUY)
        oid = order.get("groww_order_id", "N/A")
        status = order.get("order_status", "UNKNOWN")
        
        # Try to get actual fill price from order details
        actual_entry = entry_price
        if oid and oid != "N/A":
            time.sleep(0.5)  # Wait for order to process
            order_info = get_order_details(oid)
            if order_info and order_info.get("avg_price", 0) > 0:
                actual_entry = order_info["avg_price"]
                stop = actual_entry * (1 - STOP_PCT)  # Recalculate stop with actual price
                print(f"   📝 {sym}: Actual fill price: ₹{actual_entry:.2f}")
        
        positions[sym] = {
            "entry": actual_entry,
            "stop": stop,
            "qty": qty,
            "weekly_sma": signal["weekly_sma"],
            "weekly_rsi": signal["weekly_rsi"],
            "entry_date": datetime.now().isoformat(),
            "order_id": oid,
        }
        
        print(f"   ✅ {sym}: BUY {qty} @ ₹{actual_entry:.2f} | Stop: ₹{stop:.2f} | SMA Target: ₹{signal['weekly_sma']:.2f} | RSI: {signal['weekly_rsi']:.1f} [{oid}:{status}]")
        placed += 1
    except Exception as e:
        print(f"   ❌ {sym}: {e}")
    
    time.sleep(0.3)

save_json(POSITIONS_FILE, positions)

# Mark this week as entered
signals_state["last_entry_week"] = current_week
save_json(SIGNALS_FILE, signals_state)

print(f"\n🎯 Placed: {placed}")


# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("📊 WEEKLY GREEN BB SUMMARY")
print("=" * 60)
print(f"   Exits Executed: {len(exits)}")
print(f"   New Entries: {placed}")
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
        sma = pos.get("weekly_sma", 0)
        print(f"   {sym}: ₹{entry:.2f} → ₹{ltp:.2f} ({pnl:+.2f}%) | SMA Target: ₹{sma:.2f}")
        time.sleep(0.05)

print("\n✅ Strategy execution complete")
