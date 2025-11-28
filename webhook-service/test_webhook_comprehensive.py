#!/usr/bin/env python3
"""
Comprehensive Test Suite for Webhook Service
Tests every component of the webhook service in detail
"""

import os
import sys
import json
import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from dotenv import load_dotenv

# Add service to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables from .env FIRST before any other imports
load_dotenv(Path(__file__).parent / ".env")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")

# ============================================================================
# TEST 1: TELEGRAM CREDENTIALS AND CONNECTIVITY
# ============================================================================

async def test_telegram_credentials():
    """Test Telegram bot token and chat ID validity"""
    logger.info("\n" + "="*80)
    logger.info("TEST 1: TELEGRAM CREDENTIALS AND CONNECTIVITY")
    logger.info("="*80)
    
    from telegram_notifier import TelegramNotifier
    
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    logger.info(f"✓ Bot Token Present: {bool(bot_token)}")
    logger.info(f"✓ Chat ID Present: {bool(chat_id)}")
    logger.info(f"✓ Bot Token (first 30 chars): {bot_token[:30] if bot_token else 'N/A'}...")
    logger.info(f"✓ Chat ID: {chat_id}")
    
    # Create notifier and test
    notifier = TelegramNotifier(bot_token, chat_id)
    logger.info(f"✓ Notifier Enabled: {notifier.enabled}")
    
    if notifier.enabled:
        # Test message send
        test_msg = f"✅ **Webhook Service Test** - Credentials Valid\n⏰ {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')}"
        result = await notifier.send_message(test_msg)
        logger.info(f"✓ Test Message Sent: {result}")
        return result
    else:
        logger.error("✗ Telegram notifier disabled!")
        return False


# ============================================================================
# TEST 2: DHAN AUTHENTICATION
# ============================================================================

async def test_dhan_authentication():
    """Test DHAN token generation and validation"""
    logger.info("\n" + "="*80)
    logger.info("TEST 2: DHAN AUTHENTICATION")
    logger.info("="*80)
    
    from dhan_auth import load_auth_from_env
    
    try:
        dhan_auth = load_auth_from_env()
        if not dhan_auth:
            logger.error("✗ Failed to load DHAN auth from environment")
            return False
        
        logger.info("✓ DHAN auth loaded from environment")
        
        # Try to get a valid token
        token = await dhan_auth.get_valid_token(auto_refresh=False)
        if token:
            logger.info("✓ Valid DHAN token obtained (not refreshed)")
            logger.info(f"  Token (first 50 chars): {token[:50]}...")
            return True
        else:
            logger.warning("⚠ No valid token in Secret Manager, will attempt refresh")
            token = await dhan_auth.get_valid_token(auto_refresh=True)
            if token:
                logger.info("✓ Fresh DHAN token generated via auto-refresh")
                logger.info(f"  Token (first 50 chars): {token[:50]}...")
                return True
            else:
                logger.error("✗ Failed to generate DHAN token")
                return False
    except Exception as e:
        logger.error(f"✗ DHAN auth test failed: {e}")
        return False


# ============================================================================
# TEST 3: WEBHOOK PAYLOAD VALIDATION
# ============================================================================

def test_webhook_payload_validation():
    """Test webhook payload parsing and validation"""
    logger.info("\n" + "="*80)
    logger.info("TEST 3: WEBHOOK PAYLOAD VALIDATION")
    logger.info("="*80)
    
    from pydantic import ValidationError
    from app import WebhookPayload, OrderLeg, OrderMetadata
    
    # Valid payload
    valid_payload = {
        "secret": "GTcl4",
        "alertType": "multi_leg_order",
        "order_legs": [
            {
                "transactionType": "B",
                "orderType": "MKT",
                "quantity": "1",
                "exchange": "NSE_DLY",
                "symbol": "INFY",
                "instrument": "EQ",
                "productType": "C",
                "sort_order": "1",
                "price": "0",
                "amoTime": "PRE_OPEN",
                "meta": {
                    "interval": "1D",
                    "time": "2025-11-27T09:15:00Z",
                    "timenow": "2025-11-27T09:15:00Z"
                }
            }
        ]
    }
    
    try:
        payload = WebhookPayload(**valid_payload)
        logger.info("✓ Valid payload parsed successfully")
        logger.info(f"  Alert Type: {payload.alertType}")
        logger.info(f"  Order Legs: {len(payload.order_legs)}")
        logger.info(f"  First Leg: {payload.order_legs[0].transactionType} {payload.order_legs[0].quantity} {payload.order_legs[0].symbol}")
        return True
    except ValidationError as e:
        logger.error(f"✗ Valid payload failed validation: {e}")
        return False
    
    # Test invalid payload (missing required field)
    invalid_payload = {
        "secret": "GTcl4",
        "alertType": "multi_leg_order",
        "order_legs": []  # Empty legs
    }
    
    try:
        payload = WebhookPayload(**invalid_payload)
        logger.error("✗ Invalid payload should have failed validation")
        return False
    except ValidationError:
        logger.info("✓ Invalid payload correctly rejected")
        return True


# ============================================================================
# TEST 4: SIGNAL QUEUE FUNCTIONALITY
# ============================================================================

def test_signal_queue():
    """Test signal queue for AMO/holiday orders"""
    logger.info("\n" + "="*80)
    logger.info("TEST 4: SIGNAL QUEUE FUNCTIONALITY")
    logger.info("="*80)
    
    from signal_queue import SignalQueue
    
    try:
        queue = SignalQueue(db_path=":memory:")  # Use in-memory DB for testing
        logger.info("✓ Signal queue initialized")
        
        # Create a test signal
        signal_data = {
            "alert_type": "multi_leg_order",
            "payload": {"test": "data"},
            "source_ip": "127.0.0.1",
            "scheduled_time": datetime.now(IST).isoformat()
        }
        
        signal_id = queue.queue_signal(**signal_data)
        logger.info(f"✓ Signal queued successfully (ID: {signal_id})")
        
        # Retrieve signal
        signal = queue.get_signal(signal_id)
        if signal:
            logger.info(f"✓ Signal retrieved: {signal['status']}")
            return True
        else:
            logger.error(f"✗ Signal not found")
            return False
    except Exception as e:
        logger.error(f"✗ Signal queue test failed: {e}")
        return False


# ============================================================================
# TEST 5: TRADING CALENDAR
# ============================================================================

def test_trading_calendar():
    """Test trading calendar functions"""
    logger.info("\n" + "="*80)
    logger.info("TEST 5: TRADING CALENDAR")
    logger.info("="*80)
    
    from trading_calendar import get_market_status, is_trading_day, get_next_trading_day
    
    try:
        # Current status
        status = get_market_status()
        logger.info(f"✓ Current market status: {status}")
        
        # Trading day check
        today = datetime.now(IST).date()
        is_trading = is_trading_day(today)
        logger.info(f"✓ Is today ({today}) a trading day? {is_trading}")
        
        # Next trading day
        next_day = get_next_trading_day(today)
        logger.info(f"✓ Next trading day from {today}: {next_day}")
        
        return True
    except Exception as e:
        logger.error(f"✗ Trading calendar test failed: {e}")
        return False


# ============================================================================
# TEST 6: DHAN CLIENT - SYMBOL RESOLUTION
# ============================================================================

def test_dhan_symbol_resolution():
    """Test DHAN client's ability to resolve symbols to security IDs"""
    logger.info("\n" + "="*80)
    logger.info("TEST 6: DHAN CLIENT - SYMBOL RESOLUTION")
    logger.info("="*80)
    
    from dhan_client import DhanClient
    
    try:
        # Use a dummy token for testing
        client = DhanClient(access_token="dummy_token")
        logger.info("✓ DhanClient created")
        
        # Try to resolve a common symbol
        symbol = "INFY"
        exchange = "NSE_DLY"
        security_id = client.get_security_id(symbol, exchange)
        
        if security_id:
            logger.info(f"✓ Security ID resolved: {symbol} @ {exchange} = {security_id}")
            return True
        else:
            logger.warning(f"⚠ Could not resolve {symbol} @ {exchange} (CSV may not be loaded)")
            return False
    except Exception as e:
        logger.error(f"✗ Symbol resolution test failed: {e}")
        return False


# ============================================================================
# TEST 7: ENVIRONMENT VARIABLES
# ============================================================================

def test_environment_variables():
    """Test that all required environment variables are set"""
    logger.info("\n" + "="*80)
    logger.info("TEST 7: ENVIRONMENT VARIABLES")
    logger.info("="*80)
    
    required_vars = {
        "WEBHOOK_SECRET": "Required for webhook authentication",
        "TELEGRAM_BOT_TOKEN": "Required for Telegram notifications",
        "TELEGRAM_CHAT_ID": "Required for Telegram notifications",
        "DHAN_CLIENT_ID": "Required for DHAN API",
        "DHAN_API_KEY": "Required for DHAN OAuth",
        "DHAN_API_SECRET": "Required for DHAN OAuth",
        "DHAN_USER_ID": "Required for DHAN auto-refresh",
        "DHAN_PASSWORD": "Required for DHAN auto-refresh",
        "DHAN_PIN": "Required for DHAN auto-refresh",
        "DHAN_TOTP_SECRET": "Required for DHAN auto-refresh",
    }
    
    all_present = True
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            masked_value = value[:20] + "..." if len(value) > 20 else value
            logger.info(f"✓ {var}: {masked_value}")
        else:
            logger.warning(f"✗ {var}: NOT SET - {description}")
            all_present = False
    
    return all_present


# ============================================================================
# TEST 8: CSV LOGGING
# ============================================================================

def test_csv_logging():
    """Test CSV log file functionality"""
    logger.info("\n" + "="*80)
    logger.info("TEST 8: CSV LOGGING")
    logger.info("="*80)
    
    from app import init_csv_log, log_order_to_csv
    from app import OrderLeg
    
    try:
        # Initialize CSV log
        init_csv_log()
        logger.info("✓ CSV log initialized")
        
        # Create a test leg object
        class TestLeg:
            symbol = "TEST"
            exchange = "NSE_DLY"
            transactionType = "B"
            quantity = 1
            orderType = "MKT"
            productType = "C"
            price = 100
        
        leg = TestLeg()
        
        # Log an order
        log_order_to_csv(
            alert_type="test_alert",
            leg_number=1,
            leg=leg,
            status="test",
            message="Test log entry",
            order_id="TEST123"
        )
        logger.info("✓ Test order logged to CSV")
        
        # Check if file exists and has content
        csv_path = os.getenv("CSV_LOG_PATH", "/app/webhook_orders.csv")
        if os.path.exists(csv_path):
            with open(csv_path, 'r') as f:
                lines = f.readlines()
                logger.info(f"✓ CSV file exists with {lines.__len__()} lines")
                return True
        else:
            logger.warning(f"⚠ CSV file not found at {csv_path}")
            return False
    except Exception as e:
        logger.error(f"✗ CSV logging test failed: {e}")
        return False


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

async def run_all_tests():
    """Run all tests and generate report"""
    logger.info("\n\n")
    logger.info("╔" + "="*78 + "╗")
    logger.info("║" + " "*78 + "║")
    logger.info("║" + "  COMPREHENSIVE WEBHOOK SERVICE TEST SUITE".center(78) + "║")
    logger.info("║" + " "*78 + "║")
    logger.info("╚" + "="*78 + "╝")
    
    results = {}
    
    # Run synchronous tests
    logger.info("\n📋 Running synchronous tests...")
    results["Telegram Credentials"] = await test_telegram_credentials()
    results["DHAN Authentication"] = await test_dhan_authentication()
    results["Webhook Payload Validation"] = test_webhook_payload_validation()
    results["Signal Queue"] = test_signal_queue()
    results["Trading Calendar"] = test_trading_calendar()
    results["DHAN Symbol Resolution"] = test_dhan_symbol_resolution()
    results["Environment Variables"] = test_environment_variables()
    results["CSV Logging"] = test_csv_logging()
    
    # Print summary
    logger.info("\n" + "="*80)
    logger.info("TEST SUMMARY")
    logger.info("="*80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{status} - {test_name}")
    
    logger.info("="*80)
    logger.info(f"Results: {passed}/{total} tests passed ({100*passed//total}%)")
    logger.info("="*80)
    
    if passed == total:
        logger.info("\n🎉 ALL TESTS PASSED! Webhook service is healthy.")
        return 0
    else:
        logger.info(f"\n⚠️  {total - passed} test(s) failed. Review logs above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
