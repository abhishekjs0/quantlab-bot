"""
NSE/BSE Trading Calendar
Dynamic calendar for Indian stock market trading hours and holidays
All times in IST (Indian Standard Time)
"""

from datetime import datetime, time, date
from zoneinfo import ZoneInfo
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# IST timezone
IST = ZoneInfo("Asia/Kolkata")

# Market Sessions (IST)
class MarketSession:
    """NSE/BSE market session timings"""
    
    # Pre-market session
    PRE_OPEN_START = time(9, 0, 0)      # 9:00 AM
    PRE_OPEN_END = time(9, 8, 0)        # 9:08 AM
    
    # Normal trading session
    MARKET_OPEN = time(9, 15, 0)        # 9:15 AM
    MARKET_CLOSE = time(15, 30, 0)      # 3:30 PM
    
    # Post-market session
    POST_MARKET_START = time(15, 40, 0)  # 3:40 PM
    POST_MARKET_END = time(16, 0, 0)     # 4:00 PM
    
    # AMO order acceptance
    AMO_START = time(17, 0, 0)           # 5:00 PM (after market close)
    AMO_END = time(8, 59, 0)             # 8:59 AM (next day, before pre-open)


# NSE/BSE Trading Holidays for 2025
# Source: https://www.nseindia.com/resources/exchange-communication-holidays
TRADING_HOLIDAYS_2025 = [
    date(2025, 1, 26),   # Republic Day (Sunday)
    date(2025, 2, 26),   # Mahashivratri
    date(2025, 3, 14),   # Holi
    date(2025, 3, 31),   # Id-Ul-Fitr (Ramadan Eid)
    date(2025, 4, 10),   # Mahavir Jayanti
    date(2025, 4, 14),   # Dr. Baba Saheb Ambedkar Jayanti
    date(2025, 4, 18),   # Good Friday
    date(2025, 5, 1),    # Maharashtra Day
    date(2025, 6, 7),    # Id-Ul-Adha (Bakri Eid)
    date(2025, 7, 7),    # Muharram
    date(2025, 8, 15),   # Independence Day
    date(2025, 8, 27),   # Ganesh Chaturthi
    date(2025, 10, 2),   # Mahatma Gandhi Jayanti
    date(2025, 10, 21),  # Diwali Laxmi Pujan (Muhurat Trading in evening)
    date(2025, 10, 22),  # Diwali Balipratipada
    date(2025, 11, 5),   # Guru Nanak Jayanti
    date(2025, 12, 25),  # Christmas
]

# Extend with 2026 holidays (update when NSE publishes official calendar)
TRADING_HOLIDAYS_2026 = [
    date(2026, 1, 26),   # Republic Day
    date(2026, 2, 16),   # Mahashivratri (tentative)
    date(2026, 3, 3),    # Holi (tentative)
    date(2026, 3, 21),   # Id-Ul-Fitr (tentative)
    date(2026, 3, 30),   # Mahavir Jayanti (tentative)
    date(2026, 4, 3),    # Good Friday (tentative)
    date(2026, 4, 14),   # Dr. Baba Saheb Ambedkar Jayanti
    date(2026, 5, 1),    # Maharashtra Day
    date(2026, 5, 28),   # Id-Ul-Adha (tentative)
    date(2026, 6, 17),   # Muharram (tentative)
    date(2026, 8, 15),   # Independence Day
    date(2026, 9, 16),   # Ganesh Chaturthi (tentative)
    date(2026, 10, 2),   # Mahatma Gandhi Jayanti
    date(2026, 10, 25),  # Dussehra (tentative)
    date(2026, 11, 11),  # Diwali (tentative)
    date(2026, 11, 24),  # Guru Nanak Jayanti (tentative)
    date(2026, 12, 25),  # Christmas
]

# Combine all holidays
ALL_HOLIDAYS = set(TRADING_HOLIDAYS_2025 + TRADING_HOLIDAYS_2026)


def is_trading_day(check_date: Optional[date] = None) -> bool:
    """
    Check if given date is a trading day (not weekend, not holiday)
    
    Args:
        check_date: Date to check (default: today in IST)
        
    Returns:
        True if trading day, False otherwise
    """
    if check_date is None:
        check_date = datetime.now(IST).date()
    
    # Check if weekend (Saturday=5, Sunday=6)
    if check_date.weekday() >= 5:
        logger.debug(f"📅 {check_date} is weekend (not trading day)")
        return False
    
    # Check if holiday
    if check_date in ALL_HOLIDAYS:
        logger.debug(f"📅 {check_date} is holiday (not trading day)")
        return False
    
    return True


def is_market_open(check_time: Optional[datetime] = None) -> bool:
    """
    Check if market is currently open for normal trading
    
    Args:
        check_time: Datetime to check (default: now in IST)
        
    Returns:
        True if market is open, False otherwise
    """
    if check_time is None:
        check_time = datetime.now(IST)
    
    # Check if trading day
    if not is_trading_day(check_time.date()):
        return False
    
    # Check if within trading hours
    current_time = check_time.time()
    if MarketSession.MARKET_OPEN <= current_time <= MarketSession.MARKET_CLOSE:
        return True
    
    return False


def is_pre_market(check_time: Optional[datetime] = None) -> bool:
    """
    Check if currently in pre-market session
    
    Args:
        check_time: Datetime to check (default: now in IST)
        
    Returns:
        True if in pre-market, False otherwise
    """
    if check_time is None:
        check_time = datetime.now(IST)
    
    if not is_trading_day(check_time.date()):
        return False
    
    current_time = check_time.time()
    return MarketSession.PRE_OPEN_START <= current_time <= MarketSession.PRE_OPEN_END


def is_post_market(check_time: Optional[datetime] = None) -> bool:
    """
    Check if currently in post-market session
    
    Args:
        check_time: Datetime to check (default: now in IST)
        
    Returns:
        True if in post-market, False otherwise
    """
    if check_time is None:
        check_time = datetime.now(IST)
    
    if not is_trading_day(check_time.date()):
        return False
    
    current_time = check_time.time()
    return MarketSession.POST_MARKET_START <= current_time <= MarketSession.POST_MARKET_END


def is_amo_window(check_time: Optional[datetime] = None) -> bool:
    """
    Check if currently in AMO (After Market Order) window
    AMO window is 5:00 PM to 8:59 AM next trading day
    
    Args:
        check_time: Datetime to check (default: now in IST)
        
    Returns:
        True if in AMO window, False otherwise
    """
    if check_time is None:
        check_time = datetime.now(IST)
    
    current_time = check_time.time()
    
    # Evening AMO window (5:00 PM onwards)
    if current_time >= MarketSession.AMO_START:
        return True
    
    # Morning AMO window (until 8:59 AM)
    if current_time <= MarketSession.AMO_END:
        # Check if today is a trading day
        return is_trading_day(check_time.date())
    
    return False


def get_market_status(check_time: Optional[datetime] = None) -> Tuple[str, str]:
    """
    Get comprehensive market status
    
    Args:
        check_time: Datetime to check (default: now in IST)
        
    Returns:
        Tuple of (status, message)
        Status: "OPEN" | "PRE_MARKET" | "POST_MARKET" | "CLOSED" | "HOLIDAY" | "WEEKEND" | "AMO_WINDOW"
    """
    if check_time is None:
        check_time = datetime.now(IST)
    
    check_date = check_time.date()
    
    # Check if weekend
    if check_date.weekday() >= 5:
        day_name = check_date.strftime("%A")
        return ("WEEKEND", f"{day_name} - Market closed")
    
    # Check if holiday
    if check_date in ALL_HOLIDAYS:
        return ("HOLIDAY", f"Trading holiday - Market closed")
    
    # Check market sessions
    if is_market_open(check_time):
        time_str = check_time.strftime("%I:%M %p IST")
        return ("OPEN", f"Market open - Normal trading session ({time_str})")
    
    if is_pre_market(check_time):
        return ("PRE_MARKET", "Pre-market session (9:00 AM - 9:08 AM)")
    
    if is_post_market(check_time):
        return ("POST_MARKET", "Post-market session (3:40 PM - 4:00 PM)")
    
    if is_amo_window(check_time):
        return ("AMO_WINDOW", "AMO window - Orders will execute next trading day")
    
    # Market closed (outside all sessions)
    current_time = check_time.time()
    if current_time < MarketSession.PRE_OPEN_START:
        return ("CLOSED", "Market closed - Opens at 9:00 AM")
    elif current_time > MarketSession.POST_MARKET_END:
        return ("CLOSED", "Market closed - AMO window starts at 5:00 PM")
    else:
        return ("CLOSED", "Market closed")


def get_next_trading_day(from_date: Optional[date] = None) -> date:
    """
    Get the next trading day after given date
    
    Args:
        from_date: Starting date (default: today)
        
    Returns:
        Next trading day
    """
    if from_date is None:
        from_date = datetime.now(IST).date()
    
    next_day = from_date
    while True:
        # Move to next day
        from datetime import timedelta
        next_day = next_day + timedelta(days=1)
        
        # Check if it's a trading day
        if is_trading_day(next_day):
            return next_day


def should_accept_amo_order(check_time: Optional[datetime] = None) -> Tuple[bool, str]:
    """
    Determine if AMO orders should be accepted at given time
    
    Args:
        check_time: Datetime to check (default: now in IST)
        
    Returns:
        Tuple of (should_accept, reason)
    """
    if check_time is None:
        check_time = datetime.now(IST)
    
    status, message = get_market_status(check_time)
    
    # Accept AMO orders during:
    # 1. AMO window (5:00 PM - 8:59 AM next trading day)
    # 2. Market closed on trading day (before pre-open or after post-market)
    # 3. Weekend/Holiday (for next trading day)
    
    if status == "AMO_WINDOW":
        next_day = get_next_trading_day(check_time.date())
        return (True, f"AMO accepted - Will execute on {next_day.strftime('%Y-%m-%d')}")
    
    if status in ["HOLIDAY", "WEEKEND"]:
        next_day = get_next_trading_day(check_time.date())
        return (True, f"AMO accepted - Will execute on next trading day {next_day.strftime('%Y-%m-%d')}")
    
    if status == "CLOSED":
        # Between market close and 5 PM, we can still accept AMO for next day
        current_time = check_time.time()
        if current_time > MarketSession.POST_MARKET_END:
            next_day = get_next_trading_day(check_time.date())
            return (True, f"AMO accepted - Will execute on {next_day.strftime('%Y-%m-%d')}")
    
    # During market hours, prefer regular orders
    if status == "OPEN":
        return (False, "Market is open - Use regular orders instead of AMO")
    
    # Pre-market or post-market, can use AMO but not ideal
    if status in ["PRE_MARKET", "POST_MARKET"]:
        return (True, f"AMO accepted during {status.lower().replace('_', '-')}")
    
    # Default: accept AMO
    return (True, "AMO accepted")


def get_upcoming_holidays(count: int = 5, from_date: Optional[date] = None) -> list[date]:
    """
    Get upcoming trading holidays
    
    Args:
        count: Number of holidays to return
        from_date: Starting date (default: today)
        
    Returns:
        List of upcoming holiday dates
    """
    if from_date is None:
        from_date = datetime.now(IST).date()
    
    upcoming = [h for h in sorted(ALL_HOLIDAYS) if h >= from_date]
    return upcoming[:count]


# Convenience function for logging
def log_market_status():
    """Log current market status"""
    status, message = get_market_status()
    
    status_emoji = {
        "OPEN": "🟢",
        "PRE_MARKET": "🟡",
        "POST_MARKET": "🟡",
        "CLOSED": "🔴",
        "HOLIDAY": "📅",
        "WEEKEND": "📅",
        "AMO_WINDOW": "🌙"
    }
    
    emoji = status_emoji.get(status, "❓")
    logger.info(f"{emoji} Market Status: {message}")
    
    # Log if AMO orders should be accepted
    should_accept, reason = should_accept_amo_order()
    if should_accept:
        logger.info(f"✅ AMO Orders: {reason}")
    else:
        logger.info(f"⚠️  AMO Orders: {reason}")


if __name__ == "__main__":
    # Test the calendar
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 80)
    print("NSE/BSE Trading Calendar - Status Report")
    print("=" * 80)
    print()
    
    now = datetime.now(IST)
    print(f"📅 Current Time: {now.strftime('%Y-%m-%d %I:%M:%S %p %Z')}")
    print()
    
    # Market status
    status, message = get_market_status()
    print(f"🏛️  Market Status: {status}")
    print(f"   {message}")
    print()
    
    # Trading day check
    if is_trading_day():
        print("✅ Today is a trading day")
    else:
        print("❌ Today is NOT a trading day")
        next_day = get_next_trading_day()
        print(f"   Next trading day: {next_day.strftime('%Y-%m-%d %A')}")
    print()
    
    # AMO order acceptance
    should_accept, reason = should_accept_amo_order()
    if should_accept:
        print(f"✅ AMO Orders: ACCEPTED")
        print(f"   {reason}")
    else:
        print(f"❌ AMO Orders: NOT RECOMMENDED")
        print(f"   {reason}")
    print()
    
    # Session checks
    print("⏰ Session Status:")
    print(f"   Pre-market (9:00-9:08 AM):     {'✅ Active' if is_pre_market() else '❌ Inactive'}")
    print(f"   Normal trading (9:15-3:30 PM): {'✅ Active' if is_market_open() else '❌ Inactive'}")
    print(f"   Post-market (3:40-4:00 PM):    {'✅ Active' if is_post_market() else '❌ Inactive'}")
    print(f"   AMO window (5:00 PM-8:59 AM):  {'✅ Active' if is_amo_window() else '❌ Inactive'}")
    print()
    
    # Upcoming holidays
    print("📅 Upcoming Trading Holidays:")
    for i, holiday in enumerate(get_upcoming_holidays(count=5), 1):
        print(f"   {i}. {holiday.strftime('%Y-%m-%d %A')}")
    print()
    
    print("=" * 80)
