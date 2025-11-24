#!/usr/bin/env python3
"""
TradingView Webhook Service for Cloud Deployment
Standalone FastAPI application for receiving TradingView alerts and executing Dhan orders
"""

import os
import logging
import json
import csv
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from contextlib import asynccontextmanager
from typing import Optional
from concurrent.futures import ProcessPoolExecutor
from pydantic import BaseModel, Field, field_validator
from fastapi import FastAPI, Request, HTTPException, status, BackgroundTasks
from fastapi.responses import JSONResponse
import uvicorn
from dhanhq import dhanhq
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import Dhan client and authentication
from dhan_client import DhanClient
from dhan_auth import DhanAuth, load_auth_from_env
from telegram_notifier import get_notifier
from signal_queue import SignalQueue, should_queue_signal, execute_queued_signal
from trading_calendar import (
    get_market_status,
    is_trading_day,
    should_accept_amo_order,
    get_next_trading_day,
    log_market_status
)

# IST timezone
IST = ZoneInfo("Asia/Kolkata")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment configuration
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "GTcl4")
PORT = int(os.getenv("PORT", "8080"))  # Cloud Run uses PORT env variable
HOST = os.getenv("HOST", "0.0.0.0")
ENABLE_DHAN = os.getenv("ENABLE_DHAN", "false").lower() == "true"
CSV_LOG_PATH = os.getenv("CSV_LOG_PATH", "/app/webhook_orders.csv")  # Log file path
AUTO_HEALTH_CHECK = os.getenv("AUTO_HEALTH_CHECK", "true").lower() == "true"  # Auto check /ready
HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", "21600"))  # 6 hours

# CSV logging setup
def init_csv_log():
    """Initialize CSV log file with headers if it doesn't exist"""
    csv_path = Path(CSV_LOG_PATH)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not csv_path.exists():
        with open(CSV_LOG_PATH, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'alert_type', 'leg_number', 'symbol', 'exchange',
                'transaction_type', 'quantity', 'order_type', 'product_type',
                'price', 'status', 'message', 'order_id', 'security_id', 'source_ip'
            ])
        logger.info(f"📝 CSV log file created: {CSV_LOG_PATH}")

def log_order_to_csv(alert_type, leg_number, leg, status, message, order_id=None, security_id=None, source_ip=None):
    """Log order details to CSV file"""
    try:
        with open(CSV_LOG_PATH, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now(IST).isoformat(),
                alert_type,
                leg_number,
                leg.symbol,
                leg.exchange,
                leg.transactionType,
                leg.quantity,
                leg.orderType,
                leg.productType,
                leg.price,
                status,
                message,
                order_id or '',
                security_id or '',
                source_ip or ''
            ])
    except Exception as e:
        logger.error(f"❌ Failed to log to CSV: {e}")

# Initialize CSV log
init_csv_log()

# Global process pool executor (initialized in lifespan)
executor: Optional[ProcessPoolExecutor] = None

# Background health check task
async def periodic_health_check():
    """Periodically check Dhan token validity and log status"""
    while True:
        try:
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
            if not ENABLE_DHAN or not dhan_auth:
                continue
                
            # Check token validity
            token = await dhan_auth.get_valid_token(auto_refresh=False)
            if token:
                logger.info("✅ Periodic health check: Dhan token is valid")
            else:
                logger.warning("⚠️  Periodic health check: Dhan token expired, will auto-refresh on next order")
                
        except Exception as e:
            logger.error(f"❌ Health check error: {e}")

# Initialize Dhan authentication and client (moved to lifespan for async support)
dhan_auth = None
dhan_client = None

# Initialize Signal Queue
signal_queue = SignalQueue(db_path="signal_queue.db")
logger.info("✅ Signal queue initialized for weekend/holiday order handling")

# Trading calendar is already imported as functions (not a class)
# Functions available: get_market_status(), is_trading_day(), etc.


# Pydantic models for request validation
class OrderMetadata(BaseModel):
    """Metadata about the alert timing and source"""
    interval: str = Field(..., description="Chart interval (e.g., 1D, 1H)")
    time: str = Field(..., description="Bar time when alert triggered")
    timenow: str = Field(..., description="Current time when alert sent")

    @field_validator('time', 'timenow')
    @classmethod
    def validate_datetime(cls, v):
        """Validate datetime format"""
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
            return v
        except ValueError:
            raise ValueError(f"Invalid datetime format: {v}")


class OrderLeg(BaseModel):
    """Individual order leg in a multi-leg order"""
    transactionType: str = Field(..., pattern="^[BS]$", description="B=Buy, S=Sell")
    orderType: str = Field(..., description="MKT, LMT, SL, SL-M")
    quantity: str = Field(..., description="Number of shares/contracts")
    exchange: str = Field(..., description="NSE, BSE, NFO, etc.")
    symbol: str = Field(..., description="Trading symbol")
    instrument: str = Field(..., description="EQ, FUT, CE, PE, etc.")
    productType: str = Field(..., description="C=CNC, I=Intraday, M=Margin")
    sort_order: str = Field(..., description="Execution order priority")
    price: str = Field(..., description="Price for limit orders")
    amoTime: str = Field(default="PRE_OPEN", pattern="^(PRE_OPEN|OPEN|OPEN_30|OPEN_60)$", description="AMO execution timing")
    meta: OrderMetadata = Field(..., description="Alert metadata")

    @field_validator('quantity', 'sort_order', 'price')
    @classmethod
    def validate_numeric_strings(cls, v):
        """Validate that numeric string fields can be converted to numbers"""
        try:
            float(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid numeric value: {v}")


class WebhookPayload(BaseModel):
    """Complete webhook payload from TradingView"""
    secret: str = Field(..., description="Authentication secret")
    alertType: str = Field(..., description="Type of alert (multi_leg_order, etc.)")
    order_legs: list[OrderLeg] = Field(..., min_length=1, description="List of order legs")

    @field_validator("alertType")
    @classmethod
    def validate_alert_type(cls, v):
        """Validate alert type"""
        allowed_types = ["multi_leg_order", "single_order", "cancel_order"]
        if v not in allowed_types:
            logger.warning(f"Unknown alert type: {v}")
        return v


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan (startup and shutdown)"""
    global executor, dhan_auth, dhan_client
    
    # Startup
    log_market_status()
    
    # Initialize Dhan authentication and client
    if ENABLE_DHAN:
        try:
            # Initialize authentication module with auto-refresh
            dhan_auth = load_auth_from_env()
            if not dhan_auth:
                logger.error("❌ Failed to load Dhan authentication from environment")
                logger.warning("Orders will be logged only, not executed")
            else:
                # Get a valid token (will auto-generate if needed) - NOW ASYNC!
                access_token = await dhan_auth.get_valid_token()
                if access_token:
                    # Initialize Dhan client with fresh token
                    dhan_client = DhanClient(access_token=access_token)
                    logger.info("✅ Dhan client initialized with auto-refreshing token - orders will be executed")
                else:
                    logger.error("❌ Failed to get valid access token")
                    logger.warning("Orders will be logged only, not executed")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Dhan authentication: {e}")
            logger.warning("Orders will be logged only, not executed")
    else:
        logger.info("ℹ️  Dhan execution disabled - orders will be logged only")
    
    # Initialize process pool for CPU-bound tasks
    num_workers = max(2, os.cpu_count() - 1) if os.cpu_count() else 2
    executor = ProcessPoolExecutor(max_workers=num_workers)
    logger.info(f"⚡ Process pool initialized: {num_workers} workers")
    
    # Start background tasks
    queue_task = asyncio.create_task(process_queue_background())
    logger.info("🔄 Signal queue processor started")
    
    health_task = None
    if AUTO_HEALTH_CHECK and ENABLE_DHAN:
        health_task = asyncio.create_task(periodic_health_check())
        logger.info(f"🔄 Auto health check enabled (interval: {HEALTH_CHECK_INTERVAL}s)")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down background tasks...")
    queue_task.cancel()
    if health_task:
        health_task.cancel()
    
    # Shutdown process pool
    if executor:
        logger.info("🛑 Shutting down process pool...")
        executor.shutdown(wait=True, cancel_futures=True)
        logger.info("✅ Process pool shut down")


# FastAPI application with lifespan
app = FastAPI(
    title="TradingView Webhook Service",
    description="Cloud-deployed webhook endpoint for TradingView alerts → Dhan AMO order execution",
    version="2.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)


# ============================================================================
# Worker Functions for ProcessPoolExecutor (Module-level for pickling)
# ============================================================================

def validate_webhook_payload_worker(payload_dict: dict) -> dict:
    """
    Validate webhook payload in worker process (CPU-bound Pydantic validation).
    Module-level function for multiprocessing compatibility.
    
    Args:
        payload_dict: Raw payload dictionary
        
    Returns:
        dict with 'status' ('success'/'error') and 'data'/'message'
    """
    try:
        # Import here to avoid pickling issues
        from pydantic import ValidationError
        
        # Validate using Pydantic model
        payload = WebhookPayload(**payload_dict)
        
        return {
            "status": "success",
            "data": payload.dict()
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "error_type": type(e).__name__
        }


def place_order_worker(
    client_id: str,
    access_token: str,
    security_id: int,
    exchange: str,
    transaction_type: str,
    quantity: int,
    order_type: str,
    product_type: str,
    price: float,
    trigger_price: float,
    amo: bool,
    amo_time: str
) -> dict:
    """
    Place order in worker process (offloads API call from main event loop).
    Module-level function for multiprocessing compatibility.
    
    Returns:
        Order result dictionary
    """
    try:
        # Import here to avoid pickling issues
        from dhan_client import DhanClient
        
        # Initialize client in worker process
        client = DhanClient(client_id, access_token)
        
        # Place order
        result = client.place_order(
            security_id=security_id,
            exchange=exchange,
            transaction_type=transaction_type,
            quantity=quantity,
            order_type=order_type,
            product_type=product_type,
            price=price,
            trigger_price=trigger_price,
            amo=amo,
            amo_time=amo_time
        )
        
        return result
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "order_id": None
        }


# ============================================================================
# API Endpoints
# ============================================================================


@app.get("/")
async def root():
    """Root endpoint - service info"""
    # Get current market status
    market_status, market_message = get_market_status()
    should_accept, accept_message = should_accept_amo_order()
    next_trading = get_next_trading_day() if not is_trading_day() else None
    
    return {
        "service": "TradingView Webhook Service",
        "version": "2.3.0",
        "status": "running",
        "endpoints": {
            "webhook": "/webhook",
            "health": "/health",
            "ready": "/ready",
            "market_status": "/market-status",
            "logs": "/logs",
            "docs": "/docs"
        },
        "config": {
            "dhan_enabled": ENABLE_DHAN,
            "auto_health_check": AUTO_HEALTH_CHECK,
            "health_check_interval": f"{HEALTH_CHECK_INTERVAL}s (6 hours)",
            "csv_logging": True,
            "amo_mode": "PRE_OPEN"  # Default AMO timing (can be overridden per order)
        },
        "market": {
            "status": market_status,
            "message": market_message,
            "amo_accepted": should_accept,
            "amo_message": accept_message,
            "next_trading_day": next_trading.isoformat() if next_trading else None
        },
        "timestamp": datetime.now(IST).isoformat()
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint for Cloud Run / monitoring systems
    Returns 200 if service is alive
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(IST).isoformat()
    }


@app.get("/market-status")
async def market_status_endpoint():
    """
    Market status endpoint - Returns NSE/BSE market status and trading calendar info
    """
    from trading_calendar import get_upcoming_holidays, is_pre_market, is_post_market, is_amo_window
    
    now = datetime.now(IST)
    market_status, market_message = get_market_status()
    should_accept, accept_message = should_accept_amo_order()
    
    return {
        "current_time": now.isoformat(),
        "market": {
            "status": market_status,
            "message": market_message,
            "is_trading_day": is_trading_day(),
            "next_trading_day": get_next_trading_day().isoformat() if not is_trading_day() else None
        },
        "sessions": {
            "pre_market": is_pre_market(),
            "normal_trading": market_status == "OPEN",
            "post_market": is_post_market(),
            "amo_window": is_amo_window()
        },
        "amo_orders": {
            "accepted": should_accept,
            "message": accept_message
        },
        "upcoming_holidays": [
            h.isoformat() for h in get_upcoming_holidays(count=5)
        ],
        "market_hours": {
            "pre_open": "09:00 - 09:08",
            "market_open": "09:15 - 15:30",
            "post_market": "15:40 - 16:00",
            "amo_window": "17:00 - 08:59 (next day)"
        }
    }


@app.get("/auth/callback")
async def oauth_callback(tokenId: str = None):
    """
    OAuth callback endpoint - receives tokenId from Dhan after successful login
    This endpoint is called by Dhan's OAuth flow with the tokenId parameter
    """
    if not tokenId:
        logger.error("❌ OAuth callback received without tokenId parameter")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "status": "error",
                "message": "Missing tokenId parameter"
            }
        )
    
    logger.info(f"✅ OAuth callback received tokenId: {tokenId[:20]}...")
    
    # Store tokenId in dhan_auth for token generation
    if dhan_auth:
        dhan_auth.set_token_id_from_callback(tokenId)
        
        # Trigger token generation with the received tokenId
        try:
            access_token = await dhan_auth.generate_new_token()
            if access_token:
                logger.info("✅ Successfully generated access token from OAuth callback")
                
                # Update global dhan_client with new token
                global dhan_client
                from dhan_client import DhanClient
                dhan_client = DhanClient(access_token=access_token)
                
                return {
                    "status": "success",
                    "message": "Access token generated successfully",
                    "timestamp": datetime.now(IST).isoformat()
                }
            else:
                logger.error("❌ Failed to generate access token from tokenId")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "status": "error",
                        "message": "Failed to generate access token"
                    }
                )
        except Exception as e:
            logger.error(f"❌ Error generating token from callback: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "status": "error",
                    "message": str(e)
                }
            )
    else:
        logger.error("❌ dhan_auth not initialized")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "error",
                "message": "Authentication module not available"
            }
        )


@app.get("/ready")
async def readiness_check():
    """
    Readiness check - confirms service is ready to process requests
    Checks if Dhan client is initialized and token is valid
    """
    ready = True
    checks = {}
    
    # Check Dhan connection if enabled
    if ENABLE_DHAN:
        if dhan_client:
            checks["dhan_client"] = "initialized"
            # Check token validity
            if dhan_auth:
                token = await dhan_auth.get_valid_token(auto_refresh=False)
                if token:
                    checks["access_token"] = "valid"
                else:
                    checks["access_token"] = "expired"
                    ready = False
            else:
                checks["access_token"] = "no_auth_module"
                ready = False
        else:
            checks["dhan_client"] = "failed"
            ready = False
    else:
        checks["dhan_client"] = "disabled"
    
    status_code = status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE
    
    return JSONResponse(
        status_code=status_code,
        content={
            "ready": ready,
            "checks": checks,
            "timestamp": datetime.now(IST).isoformat()
        }
    )


@app.get("/logs")
async def get_logs(limit: int = 100):
    """Get recent order logs from CSV file"""
    try:
        logs = []
        with open(CSV_LOG_PATH, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                logs.append(row)
        
        # Return most recent logs first
        logs = logs[-limit:]
        logs.reverse()
        
        return {
            "status": "success",
            "count": len(logs),
            "logs": logs
        }
    except FileNotFoundError:
        return {
            "status": "success",
            "count": 0,
            "logs": [],
            "message": "No logs yet"
        }
    except Exception as e:
        logger.error(f"❌ Error reading logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading logs: {str(e)}"
        )


async def process_queue_background():
    """
    Background task to process queued signals
    Runs every 5 minutes to check for pending signals ready for execution
    """
    logger.info("🔄 Queue processor background task started")
    
    while True:
        try:
            # Sleep for 5 minutes
            await asyncio.sleep(300)
            
            # Reset stuck signals (in PROCESSING > 10 minutes)
            signal_queue.reset_stuck_signals(timeout_minutes=10)
            
            # Get pending signals
            pending = signal_queue.get_pending_signals(limit=10)
            
            if not pending:
                continue
            
            # Check if we can execute (market status check without specific AMO timing)
            should_queue, reason, _ = should_queue_signal("PRE_OPEN")
            
            if should_queue:
                logger.info(
                    f"⏸️  {len(pending)} pending signals, but cannot execute yet: {reason}"
                )
                continue
            
            # Execute pending signals
            logger.info(f"🚀 Processing {len(pending)} queued signals")
            
            for signal in pending:
                try:
                    # Execute signal
                    result = await execute_signal_from_queue(signal)
                    logger.info(f"✅ Queued signal {signal['signal_id']} executed")
                    
                except Exception as e:
                    logger.error(f"❌ Error executing queued signal {signal['signal_id']}: {e}")
            
        except Exception as e:
            logger.error(f"❌ Queue processor error: {e}")
            await asyncio.sleep(60)  # Sleep 1 minute on error


async def execute_signal_from_queue(signal: dict) -> dict:
    """
    Execute a queued signal by processing its webhook payload
    
    Args:
        signal: Signal dict with signal_id and payload
        
    Returns:
        Execution result dict
    """
    signal_id = signal["signal_id"]
    payload_dict = signal["payload"]
    
    try:
        # Mark as processing
        signal_queue.mark_processing(signal_id)
        
        # Validate payload
        payload = WebhookPayload(**payload_dict)
        
        # Process order legs (same logic as webhook endpoint)
        results = []
        source_ip = "queued_signal"
        
        for idx, leg in enumerate(payload.order_legs, 1):
            logger.info(
                f"📊 Queued Order Leg {idx}/{len(payload.order_legs)}: "
                f"{leg.transactionType} {leg.quantity} {leg.symbol}"
            )
            
            if dhan_client:
                # Get security ID
                security_id = dhan_client.get_security_id(leg.symbol, leg.exchange)
                
                if not security_id:
                    result = {
                        "leg_number": idx,
                        "symbol": leg.symbol,
                        "status": "failed",
                        "message": f"Security ID not found for {leg.symbol}",
                        "order_id": None
                    }
                    results.append(result)
                    continue
                
                # Place order
                amo_timing = leg.amoTime if hasattr(leg, 'amoTime') else "PRE_OPEN"
                order_response = dhan_client.place_order(
                    security_id=security_id,
                    exchange=leg.exchange,
                    transaction_type=leg.transactionType,
                    quantity=int(leg.quantity),
                    order_type=leg.orderType,
                    product_type=leg.productType,
                    price=float(leg.price) if leg.orderType in ["LMT", "LIMIT"] else 0,
                    amo=True,
                    amo_time=amo_timing
                )
                
                results.append(order_response)
                
                # Send Telegram notification
                telegram = get_notifier()
                if telegram.enabled:
                    asyncio.create_task(telegram.notify_order_result(
                        leg_number=idx,
                        total_legs=len(payload.order_legs),
                        symbol=leg.symbol,
                        exchange=leg.exchange,
                        transaction=leg.transactionType,
                        quantity=int(leg.quantity),
                        status=order_response.get("status", "unknown"),
                        message=order_response.get("message", ""),
                        order_id=order_response.get("order_id")
                    ))
        
        # Mark as executed
        execution_result = {
            "signal_id": signal_id,
            "status": "executed",
            "results": results,
            "timestamp": datetime.now(IST).isoformat()
        }
        signal_queue.mark_executed(signal_id, execution_result)
        
        # Send summary Telegram notification
        telegram = get_notifier()
        if telegram.enabled:
            asyncio.create_task(telegram.send_message(
                f"✅ **Queued Signal Executed**\n\n"
                f"🆔 Queue ID: {signal_id}\n"
                f"📊 Orders: {len(results)}\n"
                f"⏰ Executed: {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')}"
            ))
        
        return execution_result
        
    except Exception as e:
        error_msg = f"Exception executing queued signal: {str(e)}"
        logger.error(f"❌ {error_msg}")
        signal_queue.mark_failed(signal_id, error_msg)
        
        return {
            "signal_id": signal_id,
            "status": "failed",
            "error": error_msg
        }


@app.post("/webhook")
async def receive_webhook(request: Request):
    """
    Main webhook endpoint for receiving TradingView alerts
    
    Accepts:
    - Content-Type: text/plain or application/json
    - Raw body: JSON string
    - No special headers required
    """
    try:
        # Read raw body (TradingView sends as text/plain)
        body = await request.body()
        body_str = body.decode('utf-8')
        
        logger.info(f"📨 Webhook received from {request.client.host}")
        logger.debug(f"Raw body: {body_str}")
        
        # Parse JSON from raw body
        try:
            payload_dict = json.loads(body_str)
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON payload: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid JSON format: {str(e)}"
            )
        
        # Validate payload structure using worker process (offload CPU-bound validation)
        try:
            if executor:
                # Use process pool for validation (non-blocking)
                loop = asyncio.get_event_loop()
                validation_result = await loop.run_in_executor(
                    executor,
                    validate_webhook_payload_worker,
                    payload_dict
                )
                
                if validation_result["status"] == "error":
                    logger.error(f"❌ Payload validation failed: {validation_result['message']}")
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Payload validation error: {validation_result['message']}"
                    )
                
                # Reconstruct payload from validated data
                payload = WebhookPayload(**validation_result["data"])
            else:
                # Fallback to synchronous validation if executor not available
                payload = WebhookPayload(**payload_dict)
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Payload validation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Payload validation error: {str(e)}"
            )
        
        # Verify secret
        if payload.secret != WEBHOOK_SECRET:
            logger.warning(f"⚠️  Invalid secret from {request.client.host}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook secret"
            )
        
        # Log received alert
        logger.info(f"✅ Valid webhook: {payload.alertType} with {len(payload.order_legs)} leg(s)")
        
        # Check market status and AMO acceptance
        market_status, market_message = get_market_status()
        should_accept, accept_message = should_accept_amo_order()
        
        logger.info(f"🏛️  Market Status: {market_status} - {market_message}")
        logger.info(f"{'✅' if should_accept else '⚠️ '} AMO Orders: {accept_message}")
        
        # Determine AMO timing from first order leg (or use default)
        amo_timing = payload.order_legs[0].amoTime if payload.order_legs else "PRE_OPEN"
        
        # Check if signal should be queued (weekend/holiday/after-hours)
        should_queue_sig, queue_reason, scheduled_time = should_queue_signal(amo_timing)
        
        if should_queue_sig:
            # Queue the signal for later execution
            signal_id = signal_queue.add_signal(
                payload=payload_dict,
                scheduled_time=scheduled_time,
                reason=queue_reason
            )
            
            logger.info(
                f"📥 Signal queued: ID={signal_id}, "
                f"reason={queue_reason}, "
                f"amo_timing={amo_timing}, "
                f"scheduled={scheduled_time.strftime('%Y-%m-%d %H:%M') if scheduled_time else 'TBD'}"
            )
            
            # Send Telegram notification
            telegram = get_notifier()
            if telegram.enabled:
                legs_summary = "\n".join([
                    f"  • {leg.transactionType} {leg.quantity} {leg.symbol}"
                    for leg in payload.order_legs
                ])
                asyncio.create_task(telegram.send_message(
                    f"📥 **Signal Queued**\n\n"
                    f"🆔 Queue ID: {signal_id}\n"
                    f"💬 Reason: {queue_reason}\n"
                    f"⏰ Scheduled: {scheduled_time.strftime('%Y-%m-%d %H:%M IST') if scheduled_time else 'Next trading day'}\n"
                    f"📊 Orders:\n{legs_summary}"
                ))
            
            return {
                "status": "queued",
                "signal_id": signal_id,
                "reason": queue_reason,
                "scheduled_time": scheduled_time.isoformat() if scheduled_time else None,
                "message": f"Signal queued for execution: {queue_reason}"
            }
        
        # Warn if market is open (AMO not ideal during market hours)
        if market_status == "OPEN":
            logger.warning(
                "⚠️  Market is currently OPEN. "
                "AMO orders will be placed but will execute next trading day. "
                "Consider using regular orders during market hours."
            )
        
        # Send Telegram notification about received alert
        telegram = get_notifier()
        if telegram.enabled:
            legs_summary = [
                {
                    "symbol": leg.symbol,
                    "transaction": leg.transactionType,
                    "quantity": leg.quantity,
                    "exchange": leg.exchange,
                    "order_type": leg.orderType,
                    "product_type": leg.productType
                }
                for leg in payload.order_legs
            ]
            asyncio.create_task(telegram.notify_alert_received(
                alert_type=payload.alertType,
                num_legs=len(payload.order_legs),
                source_ip=request.client.host if request.client else "unknown",
                legs_summary=legs_summary
            ))
        
        # Process each order leg
        results = []
        source_ip = request.client.host if request.client else "unknown"
        
        for idx, leg in enumerate(payload.order_legs, 1):
            logger.info(
                f"📊 Order Leg {idx}/{len(payload.order_legs)}: "
                f"{leg.transactionType} {leg.quantity} {leg.symbol} "
                f"@ {leg.exchange} ({leg.orderType})"
            )
            
            # Execute order with Dhan if enabled
            if dhan_client:
                try:
                    # Ensure we have a fresh token before placing order
                    if dhan_auth:
                        access_token = await dhan_auth.get_valid_token()
                        if access_token:
                            # Update client with fresh token if needed
                            dhan_client.access_token = access_token
                            dhan_client.dhan = dhanhq(dhan_client.client_id, access_token)
                        else:
                            logger.error("❌ Failed to get valid token, cannot place order")
                            result = {
                                "leg_number": idx,
                                "symbol": leg.symbol,
                                "transaction": leg.transactionType,
                                "quantity": leg.quantity,
                                "status": "failed",
                                "message": "Failed to refresh access token",
                                "order_id": None
                            }
                            results.append(result)
                            continue
                    
                    # Get security ID for the symbol
                    security_id = dhan_client.get_security_id(leg.symbol, leg.exchange)
                    
                    if not security_id:
                        result = {
                            "leg_number": idx,
                            "symbol": leg.symbol,
                            "transaction": leg.transactionType,
                            "quantity": leg.quantity,
                            "status": "failed",
                            "message": f"Security ID not found for {leg.symbol} on {leg.exchange}",
                            "order_id": None
                        }
                        logger.error(f"❌ {result['message']}")
                    else:
                        # SELL order validation: Check if we have sufficient quantity
                        if leg.transactionType in ["S", "SELL"]:
                            logger.info(f"🔍 Validating SELL order: checking portfolio/positions")
                            
                            qty_check = dhan_client.check_available_quantity(
                                security_id=security_id,
                                required_quantity=int(leg.quantity),
                                product_type=leg.productType
                            )
                            
                            if not qty_check["available"]:
                                result = {
                                    "leg_number": idx,
                                    "symbol": leg.symbol,
                                    "transaction": leg.transactionType,
                                    "quantity": leg.quantity,
                                    "status": "rejected",
                                    "message": f"SELL order rejected: {qty_check['reason']}",
                                    "order_id": None,
                                    "validation": qty_check
                                }
                                logger.warning(f"⚠️  {result['message']}")
                                
                                # Log rejection to CSV
                                log_order_to_csv(
                                    alert_type=payload.alertType,
                                    leg_number=idx,
                                    leg=leg,
                                    status="rejected",
                                    message=result["message"],
                                    security_id=security_id,
                                    source_ip=source_ip
                                )
                                
                                # Send Telegram notification for rejected order
                                if telegram.enabled:
                                    asyncio.create_task(telegram.notify_order_result(
                                        leg_number=idx,
                                        total_legs=len(payload.order_legs),
                                        symbol=leg.symbol,
                                        exchange=leg.exchange,
                                        transaction=leg.transactionType,
                                        quantity=int(leg.quantity),
                                        status="rejected",
                                        message=result["message"],
                                        validation_details=qty_check
                                    ))
                                
                                results.append(result)
                                continue
                            else:
                                logger.info(
                                    f"✅ SELL validation passed: "
                                    f"{qty_check['available_quantity']} available, "
                                    f"{qty_check['required_quantity']} required "
                                    f"(source: {qty_check['source']})"
                                )
                        
                        # Place AMO order for next day execution (always AMO mode)
                        amo_timing = leg.amoTime if hasattr(leg, 'amoTime') else "PRE_OPEN"
                        logger.info(f"🌙 Placing AMO order for next day execution (timing: {amo_timing})")
                        
                        # Use worker process for order placement (offload API call)
                        if executor:
                            loop = asyncio.get_event_loop()
                            order_response = await loop.run_in_executor(
                                executor,
                                place_order_worker,
                                dhan_client.client_id,
                                dhan_client.access_token,
                                security_id,
                                leg.exchange,
                                leg.transactionType,
                                int(leg.quantity),
                                leg.orderType,
                                leg.productType,
                                float(leg.price) if leg.orderType in ["LMT", "LIMIT"] else 0,
                                0,  # trigger_price
                                True,  # amo
                                amo_timing  # amo_time
                            )
                        else:
                            # Fallback to synchronous call if executor not available
                            order_response = dhan_client.place_order(
                                security_id=security_id,
                                exchange=leg.exchange,
                                transaction_type=leg.transactionType,
                                quantity=int(leg.quantity),
                                order_type=leg.orderType,
                                product_type=leg.productType,
                                price=float(leg.price) if leg.orderType in ["LMT", "LIMIT"] else 0,
                                amo=True,  # Always AMO
                                amo_time=amo_timing,  # Use specified AMO timing
                                tag=f"TV-{payload.alertType}-{idx}"
                            )
                        
                        result = {
                            "leg_number": idx,
                            "symbol": leg.symbol,
                            "transaction": leg.transactionType,
                            "quantity": leg.quantity,
                            "status": order_response["status"],
                            "message": order_response["message"],
                            "order_id": order_response.get("order_id")
                        }
                        
                        if result["status"] == "success":
                            logger.info(f"✅ AMO Order placed: {result['order_id']} (executes next day)")
                        else:
                            logger.error(f"❌ Order failed: {result['message']}")
                        
                        # Send Telegram notification for order result
                        if telegram.enabled:
                            asyncio.create_task(telegram.notify_order_result(
                                leg_number=idx,
                                total_legs=len(payload.order_legs),
                                symbol=leg.symbol,
                                exchange=leg.exchange,
                                transaction=leg.transactionType,
                                quantity=int(leg.quantity),
                                status=result["status"],
                                message=result["message"],
                                order_id=result.get("order_id")
                            ))
                        
                        # Log to CSV
                        log_order_to_csv(
                            alert_type=payload.alertType,
                            leg_number=idx,
                            leg=leg,
                            status=result["status"],
                            message=result["message"],
                            order_id=result.get("order_id"),
                            security_id=security_id,
                            source_ip=source_ip
                        )
                        
                except Exception as e:
                    logger.error(f"❌ Error executing order leg {idx}: {e}", exc_info=True)
                    result = {
                        "leg_number": idx,
                        "symbol": leg.symbol,
                        "transaction": leg.transactionType,
                        "quantity": leg.quantity,
                        "status": "error",
                        "message": str(e),
                        "order_id": None
                    }
                    
                    # Send Telegram notification for error
                    if telegram.enabled:
                        asyncio.create_task(telegram.notify_order_result(
                            leg_number=idx,
                            total_legs=len(payload.order_legs),
                            symbol=leg.symbol,
                            exchange=leg.exchange,
                            transaction=leg.transactionType,
                            quantity=int(leg.quantity),
                            status="error",
                            message=str(e)
                        ))
                    
                    # Log error to CSV
                    log_order_to_csv(
                        alert_type=payload.alertType,
                        leg_number=idx,
                        leg=leg,
                        status="error",
                        message=str(e),
                        source_ip=source_ip
                    )
            else:
                # Dhan not enabled, just acknowledge and log
                result = {
                    "leg_number": idx,
                    "symbol": leg.symbol,
                    "transaction": leg.transactionType,
                    "quantity": leg.quantity,
                    "status": "acknowledged",
                    "message": "Order received and logged (Dhan execution disabled)",
                    "order_id": None
                }
                logger.info(f"ℹ️  Test mode - order logged but not executed")
                
                # Log to CSV even in test mode
                log_order_to_csv(
                    alert_type=payload.alertType,
                    leg_number=idx,
                    leg=leg,
                    status="acknowledged",
                    message="Dhan execution disabled",
                    source_ip=source_ip
                )
            
            results.append(result)
        
        # Send batch summary notification
        if telegram.enabled:
            successful = sum(1 for r in results if r["status"] == "success")
            failed = sum(1 for r in results if r["status"] == "failed")
            rejected = sum(1 for r in results if r["status"] == "rejected")
            asyncio.create_task(telegram.notify_batch_summary(
                alert_type=payload.alertType,
                total_legs=len(payload.order_legs),
                successful=successful,
                failed=failed,
                rejected=rejected
            ))
        
        response = {
            "status": "success",
            "message": f"Processed {len(payload.order_legs)} order leg(s)",
            "alertType": payload.alertType,
            "timestamp": datetime.now(IST).isoformat(),
            "results": results
        }
        
        logger.info(f"✅ Webhook processed successfully")
        return JSONResponse(content=response, status_code=status.HTTP_200_OK)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error processing webhook: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"❌ Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "message": "Internal server error",
            "timestamp": datetime.now(IST).isoformat()
        }
    )


if __name__ == "__main__":
    logger.info(f"🚀 Starting webhook service on {HOST}:{PORT}")
    logger.info(f"📍 Webhook endpoint: http://{HOST}:{PORT}/webhook")
    logger.info(f"❤️  Health check: http://{HOST}:{PORT}/health")
    
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="info",
        access_log=True
    )
