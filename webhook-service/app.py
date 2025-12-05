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

# Import Google Cloud Firestore for persistent logging
try:
    from google.cloud import firestore
    FIRESTORE_AVAILABLE = True
except ImportError:
    FIRESTORE_AVAILABLE = False
    logger_temp = logging.getLogger(__name__)
    logger_temp.warning("⚠️  Google Cloud Firestore not available - using CSV logging only")

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
AUTO_HEALTH_CHECK = os.getenv("AUTO_HEALTH_CHECK", "true").lower() == "true"  # Auto check /ready
HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", "21600"))  # 6 hours

# Firestore initialization
db = None
try:
    if FIRESTORE_AVAILABLE:
        db = firestore.Client(project="tradingview-webhook-prod")
        logger.info("✅ Firestore client initialized for persistent order logging")
except Exception as e:
    logger.warning(f"⚠️  Could not initialize Firestore: {e} - will use CSV logging only")
    db = None

def log_order_to_firestore(alert_type, leg_number, leg, status, message, order_id=None, security_id=None, source_ip=None):
    """Log order details to Firestore for persistent storage"""
    if not db:
        return
    
    try:
        doc_data = {
            'timestamp': datetime.now(IST),
            'alert_type': alert_type,
            'leg_number': leg_number,
            'symbol': leg.symbol,
            'exchange': leg.exchange,
            'transaction_type': leg.transactionType,
            'quantity': int(leg.quantity),
            'order_type': leg.orderType,
            'product_type': leg.productType,
            'price': float(leg.price) if leg.price else 0,
            'status': status,
            'message': message,
            'order_id': order_id or '',
            'security_id': security_id or '',
            'source_ip': source_ip or '',
            'alert_type_enum': alert_type
        }
        
        # Use timestamp as document ID for sorting and uniqueness
        doc_id = f"{datetime.now(IST).timestamp()}_{leg_number}_{leg.symbol}"
        db.collection('webhook_orders').document(doc_id).set(doc_data)
        logger.debug(f"📊 Order logged to Firestore: {doc_id}")
    except Exception as e:
        logger.error(f"❌ Failed to log to Firestore: {e}")
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

# OAuth Callback State Management
# Stores pending OAuth requests and captures tokenId from Dhan OAuth callback
_oauth_pending = {}  # {'consent_app_id': {'created_at': datetime, 'token_id': str, 'expires_at': datetime}}
OAUTH_TIMEOUT_SECONDS = 300  # 5 minutes to complete OAuth flow


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
    
    # Recover queue state (reset stuck PROCESSING signals)
    recovery_stats = signal_queue.recover_on_startup()
    logger.info(f"📊 Queue recovery: {recovery_stats}")
    
    # Initialize Dhan authentication and client
    if ENABLE_DHAN:
        try:
            # Initialize authentication module
            dhan_auth = load_auth_from_env()
            if not dhan_auth:
                logger.error("❌ Failed to load Dhan authentication from environment")
                logger.warning("Orders will be logged only, not executed")
            else:
                # Get token WITHOUT auto-refresh during startup (to avoid 60s+ timeout)
                # auto_refresh=False ensures we only check Secret Manager/memory
                # If token is expired, the cron job will refresh it
                access_token = await dhan_auth.get_valid_token(auto_refresh=False)
                if access_token:
                    # Initialize Dhan client with fresh token
                    dhan_client = DhanClient(access_token=access_token)
                    logger.info("✅ Dhan client initialized with valid token - orders will be executed")
                else:
                    logger.warning("⚠️  No valid token found during startup - service will start but orders will fail until token is refreshed")
                    logger.warning("⚠️  Call /refresh-token endpoint or wait for cron job to refresh token")
                    # Still initialize auth so /refresh-token endpoint works
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
    # Test security ID lookup with NSE_DLY to verify normalization fix
    test_result = None
    if dhan_client:
        test_result = dhan_client.get_security_id("JSWINFRA", "NSE_DLY")
    
    return {
        "status": "healthy",
        "timestamp": datetime.now(IST).isoformat(),
        "test_security_id_jswinfra_nse_dly": test_result,
        "code_version": "fresh-recreated-service"
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


@app.post("/initiate-oauth")
async def initiate_oauth():
    """
    Initiate OAuth flow - returns login URL for user to open in browser.
    
    This is the recommended way to refresh tokens - it avoids headless browser issues.
    
    Flow:
    1. User calls this endpoint (or cron job calls it)
    2. Returns a login URL
    3. User opens the URL in any browser and logs in
    4. Dhan redirects back to /auth/callback with tokenId
    5. Token is automatically saved to Secret Manager
    6. Webhook service loads new token on next startup
    
    Returns:
        {
            "status": "pending_login",
            "login_url": "https://auth.dhan.co/login/...",
            "consent_app_id": "...",
            "timeout_seconds": 300,
            "instructions": "Open login_url in your browser and complete login"
        }
    """
    if not ENABLE_DHAN or not dhan_auth:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "error",
                "message": "Dhan authentication not enabled"
            }
        )
    
    try:
        logger.info("🌐 Initiating OAuth flow (callback-based, no headless browser needed)")
        
        # Step 1: Generate consent
        consent_app_id, error_code = dhan_auth._step1_generate_consent()
        if not consent_app_id:
            # Handle specific error codes
            if error_code == "CONSENT_LIMIT_EXCEED":
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "status": "rate_limited",
                        "error_code": "CONSENT_LIMIT_EXCEED",
                        "message": "Dhan API consent limit exceeded. Wait 24 hours for reset.",
                        "solution": "This is a Dhan rate limit, not a service issue. Try again tomorrow."
                    }
                )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "status": "error",
                    "error_code": error_code,
                    "message": f"Failed to generate consent: {error_code}"
                }
            )
        
        # Store pending request with timeout
        _oauth_pending[consent_app_id] = {
            "created_at": datetime.now(IST),
            "expires_at": datetime.now(IST) + timedelta(seconds=OAUTH_TIMEOUT_SECONDS),
            "token_id": None
        }
        
        # Build login URL
        # The redirect_uri parameter tells Dhan where to send the tokenId after successful login
        redirect_uri = os.getenv("DHAN_REDIRECT_URI", "https://tradingview-webhook-cgy4m5alfq-el.a.run.app/auth/callback")
        login_url = f"https://auth.dhan.co/login/consentApp-login?consentAppId={consent_app_id}&redirect_uri={redirect_uri}"
        
        logger.info(f"✅ OAuth flow initiated")
        logger.info(f"   consentAppId: {consent_app_id}")
        logger.info(f"   login_url: {login_url}")
        logger.info(f"   timeout: {OAUTH_TIMEOUT_SECONDS}s")
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "pending_login",
                "message": "Open the login_url in your browser to log in. Dhan will redirect back here with tokenId.",
                "login_url": login_url,
                "consent_app_id": consent_app_id,
                "timeout_seconds": OAUTH_TIMEOUT_SECONDS,
                "instructions": [
                    "1. Open the login_url in your browser",
                    "2. Enter your mobile number and click Proceed",
                    "3. Enter your TOTP code and click Proceed", 
                    "4. Enter your PIN and click Proceed",
                    "5. You'll be redirected back here automatically",
                    "6. Token will be saved to Secret Manager",
                    "7. Service will use new token on next startup"
                ],
                "created_at": datetime.now(IST).isoformat(),
                "expires_at": (datetime.now(IST) + timedelta(seconds=OAUTH_TIMEOUT_SECONDS)).isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error initiating OAuth: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": str(e)
            }
        )


@app.get("/oauth-status")
async def get_oauth_status(consent_app_id: str):
    """
    Check status of an ongoing OAuth flow.
    
    Parameters:
        consent_app_id: The consent_app_id returned from /initiate-oauth
    
    Returns:
        {
            "status": "pending" or "completed",
            "token_id": "..." (if completed),
            "seconds_elapsed": 45,
            "seconds_remaining": 255,
            "created_at": "...",
            "completed_at": "..." (if completed)
        }
    """
    if consent_app_id not in _oauth_pending:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "status": "error",
                "message": f"Unknown consent_app_id: {consent_app_id}"
            }
        )
    
    request_info = _oauth_pending[consent_app_id]
    now = datetime.now(IST)
    
    return {
        "status": "completed" if request_info["token_id"] else "pending",
        "consent_app_id": consent_app_id,
        "token_id": request_info["token_id"],
        "created_at": request_info["created_at"].isoformat(),
        "expires_at": request_info["expires_at"].isoformat(),
        "seconds_elapsed": (now - request_info["created_at"]).total_seconds(),
        "seconds_remaining": max(0, (request_info["expires_at"] - now).total_seconds())
    }


@app.get("/auth/callback")
async def oauth_callback(
    consentAppId: str = None,
    tokenId: str = None,
    token_id: str = None,
    error: str = None,
    error_description: str = None
):
    """
    OAuth callback endpoint - Dhan redirects here after user successfully logs in.
    
    Dhan sends:
        ?consentAppId=<app_id>&tokenId=<token>
    
    Or on error:
        ?error=access_denied&error_description=User+cancelled
    
    This endpoint:
    1. Captures the tokenId from redirect
    2. Calls Step 3 (consume consent) to get access_token
    3. Saves token to Secret Manager
    4. Returns success/error to user
    """
    
    # Handle OAuth error response
    if error:
        error_msg = f"{error}: {error_description}" if error_description else error
        logger.error(f"❌ OAuth error: {error_msg}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "status": "error",
                "message": f"OAuth failed: {error_msg}",
                "error": error,
                "error_description": error_description
            }
        )
    
    # Validate required parameters
    if not consentAppId:
        logger.error("❌ OAuth callback missing consentAppId")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "status": "error",
                "message": "Missing consentAppId parameter"
            }
        )
    
    # Try both parameter names (tokenId and token_id)
    final_token_id = tokenId or token_id
    if not final_token_id:
        logger.error("❌ OAuth callback missing tokenId")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "status": "error",
                "message": "Missing tokenId parameter"
            }
        )
    
    # Check if this is a known pending OAuth request
    if consentAppId not in _oauth_pending:
        logger.warning(f"⚠️  OAuth callback for unknown consentAppId: {consentAppId}")
        # Still process it (might be from previous session)
    
    try:
        logger.info(f"✅ OAuth callback received")
        logger.info(f"   consentAppId: {consentAppId[:20]}...")
        logger.info(f"   tokenId: {final_token_id[:20]}...")
        
        if not dhan_auth:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "error",
                    "message": "Authentication module not available"
                }
            )
        
        # Step 3: Consume consent to get access token
        logger.info("📝 Calling Step 3: Consume consent...")
        result = dhan_auth._step3_consume_consent(final_token_id)
        
        if not result:
            logger.error("❌ Failed to consume consent")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "status": "error",
                    "message": "Failed to consume consent and get access token"
                }
            )
        
        access_token, expiry = result
        
        # Update the dhan_auth object
        dhan_auth._access_token = access_token
        dhan_auth._token_expiry = expiry
        
        # Update global dhan_client with new token
        global dhan_client
        from dhan_client import DhanClient
        dhan_client = DhanClient(access_token=access_token)
        
        # Mark OAuth request as completed
        if consentAppId in _oauth_pending:
            _oauth_pending[consentAppId]["token_id"] = final_token_id
            _oauth_pending[consentAppId]["completed_at"] = datetime.now(IST)
        
        hours_remaining = (expiry - datetime.now()).total_seconds() / 3600
        
        logger.info(f"✅ OAuth flow complete!")
        logger.info(f"   Access token obtained: {access_token[:20]}...")
        logger.info(f"   Expires: {expiry} ({hours_remaining:.1f} hours)")
        logger.info(f"   Dhan client updated and ready for orders")
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "success",
                "message": "OAuth flow completed successfully! Token obtained and saved.",
                "access_token": access_token[:30] + "...",
                "expiry": expiry.isoformat(),
                "hours_remaining": round(hours_remaining, 2),
                "dhan_client_ready": True,
                "instructions": "You can close this window. The webhook service will use the new token immediately."
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error in OAuth callback: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": str(e)
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


@app.post("/refresh-token")
async def refresh_token_endpoint(use_callback: bool = False):
    """
    Token refresh endpoint - generates new access token.
    
    Parameters:
        use_callback: If True, uses callback-based OAuth (recommended)
    
    Two modes:
    
    1. Callback Mode (RECOMMENDED):
       ?use_callback=true
       Returns login URL for user to open in browser
       User logs in, Dhan redirects back with tokenId
       No headless browser involved - 100% reliable
    
    2. Playwright Mode (Legacy Fallback):
       ?use_callback=false (or omitted)
       Attempts to use headless browser automation
       May timeout in Cloud Run
    
    Intended for:
    - Cloud Scheduler cron job (daily at 9 AM IST)
    - Manual token refresh requests
    
    Returns:
        Callback mode: login_url and instructions
        Playwright mode: success/error and new token status
    """
    if not ENABLE_DHAN or not dhan_auth:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "error",
                "message": "Dhan authentication not enabled"
            }
        )
    
    try:
        logger.info(f"🔄 Token refresh endpoint called (use_callback={use_callback})")
        
        # Check current token status (for logging)
        current_expiry = dhan_auth._token_expiry
        time_remaining = 0
        if current_expiry:
            time_remaining = (current_expiry - datetime.now()).total_seconds() / 3600
            logger.info(f"Current token expires: {current_expiry} ({time_remaining:.1f}h remaining)")
        else:
            logger.info("No current token loaded")
        
        # MODE 1: Callback-based OAuth (RECOMMENDED)
        if use_callback:
            logger.info("🌐 Using callback-based OAuth (recommended, no headless browser needed)")
            
            # Generate consent and return login URL
            consent_app_id, error_code = dhan_auth._step1_generate_consent()
            if not consent_app_id:
                # Handle rate limit specifically
                if error_code == "CONSENT_LIMIT_EXCEED":
                    return JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        content={
                            "status": "rate_limited",
                            "error_code": "CONSENT_LIMIT_EXCEED",
                            "message": "Dhan API consent limit exceeded. Wait 24 hours for reset."
                        }
                    )
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "status": "error",
                        "error_code": error_code,
                        "message": f"Failed to generate consent: {error_code}"
                    }
                )
            
            # Store pending request
            _oauth_pending[consent_app_id] = {
                "created_at": datetime.now(IST),
                "expires_at": datetime.now(IST) + timedelta(seconds=OAUTH_TIMEOUT_SECONDS),
                "token_id": None
            }
            
            redirect_uri = os.getenv("DHAN_REDIRECT_URI", "https://tradingview-webhook-cgy4m5alfq-el.a.run.app/auth/callback")
            login_url = f"https://auth.dhan.co/login/consentApp-login?consentAppId={consent_app_id}&redirect_uri={redirect_uri}"
            
            logger.info("✅ Callback mode: Return login_url to user")
            
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "status": "pending_login",
                    "mode": "callback",
                    "message": "Open login_url in browser to complete OAuth flow",
                    "login_url": login_url,
                    "consent_app_id": consent_app_id,
                    "timeout_seconds": OAUTH_TIMEOUT_SECONDS,
                    "check_status_url": f"/oauth-status?consent_app_id={consent_app_id}",
                    "instructions": [
                        "1. Open the login_url in your browser",
                        "2. Log in with Dhan credentials",
                        "3. You'll be redirected back automatically",
                        "4. Token will be saved to Secret Manager"
                    ]
                }
            )
        
        # MODE 2: Playwright headless browser (Legacy, may fail in Cloud Run)
        else:
            logger.warning("⚠️  Using Playwright mode (may timeout in Cloud Run)")
            logger.warning("💡 Tip: Use ?use_callback=true for reliable callback-based OAuth")
            
            # Try to generate new token via Playwright (may timeout)
            new_token = await dhan_auth.force_refresh_token()
            
            if new_token:
                new_expiry = dhan_auth._token_expiry
                time_remaining = (new_expiry - datetime.now()).total_seconds() / 3600 if new_expiry else 0
                
                # Update global dhan_client with new token
                global dhan_client
                from dhan_client import DhanClient
                dhan_client = DhanClient(access_token=new_token)
                
                logger.info(f"✅ Playwright refresh successful! New token expires: {new_expiry}")
                logger.info(f"   Dhan client updated and ready for orders")
                
                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content={
                        "status": "success",
                        "mode": "playwright",
                        "message": "Token successfully refreshed via headless browser",
                        "token_valid": True,
                        "expiry": new_expiry.isoformat() if new_expiry else None,
                        "hours_remaining": round(time_remaining, 2),
                        "dhan_client_ready": True,
                        "timestamp": datetime.now(IST).isoformat()
                    }
                )
            else:
                logger.error("❌ Playwright refresh failed (timeout or login error)")
                logger.info("💡 Try callback mode instead: /refresh-token?use_callback=true")
                
                return JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content={
                        "status": "error",
                        "mode": "playwright",
                        "message": "Playwright token refresh failed (timeout or login error)",
                        "recommendation": "Use callback-based OAuth instead: /refresh-token?use_callback=true",
                        "timestamp": datetime.now(IST).isoformat()
                    }
                )
            
    except Exception as e:
        logger.error(f"❌ Error in refresh token endpoint: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now(IST).isoformat()
            }
        )


@app.get("/queue-stats")
async def get_queue_stats():
    """
    Get signal queue statistics
    
    Returns counts by status (QUEUED, PROCESSING, EXECUTED, FAILED)
    and recent signals for debugging.
    """
    try:
        stats = signal_queue.get_queue_stats()
        pending = signal_queue.get_pending_signals(limit=5)
        
        # Get total and recent activity
        total = sum(stats.values())
        
        return {
            "status": "success",
            "queue_stats": {
                "total_signals": total,
                "by_status": stats,
                "pending_signals": len(pending)
            },
            "recent_pending": [
                {
                    "signal_id": s["signal_id"],
                    "received_time": s["received_time"],
                    "scheduled_time": s["scheduled_time"],
                    "status": s["status"]
                }
                for s in pending
            ],
            "timestamp": datetime.now(IST).isoformat()
        }
    except Exception as e:
        logger.error(f"❌ Error getting queue stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting queue stats: {str(e)}"
        )


@app.post("/process-queue")
async def process_queue_manual():
    """
    Manually trigger queue processing.
    
    Use this to process pending signals without waiting for the background task.
    Only processes signals during acceptable market hours (AMO window or market open).
    """
    try:
        # Reset stuck signals first
        signal_queue.reset_stuck_signals(timeout_minutes=10)
        
        # Get pending signals
        pending = signal_queue.get_pending_signals(limit=10)
        
        if not pending:
            return {
                "status": "success",
                "message": "No pending signals to process",
                "processed": 0,
                "timestamp": datetime.now(IST).isoformat()
            }
        
        # Check if we can execute
        try:
            should_queue, reason, _ = should_queue_signal("PRE_OPEN")
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error checking market status: {str(e)}",
                "timestamp": datetime.now(IST).isoformat()
            }
        
        if should_queue:
            return {
                "status": "skipped",
                "message": f"Cannot execute yet: {reason}",
                "pending_count": len(pending),
                "timestamp": datetime.now(IST).isoformat()
            }
        
        # Process signals
        results = []
        for signal in pending:
            try:
                result = await execute_signal_from_queue(signal)
                results.append({
                    "signal_id": signal["signal_id"],
                    "status": "success"
                })
                logger.info(f"✅ Queued signal {signal['signal_id']} executed via manual trigger")
            except Exception as e:
                results.append({
                    "signal_id": signal["signal_id"],
                    "status": "error",
                    "error": str(e)
                })
                logger.error(f"❌ Error executing queued signal {signal['signal_id']}: {e}")
        
        return {
            "status": "success",
            "message": f"Processed {len(results)} signals",
            "processed": len(results),
            "results": results,
            "timestamp": datetime.now(IST).isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error in manual queue processing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing queue: {str(e)}"
        )


@app.get("/logs")
async def get_logs(limit: int = 100):
    """Get recent order logs from Firestore (redirects to /logs/firestore)"""
    # Redirect to Firestore logs - CSV logging removed as it was ephemeral
    try:
        return await get_firestore_logs(limit=limit)
    except Exception as e:
        logger.error(f"❌ Error reading logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading logs: {str(e)}"
        )


@app.get("/logs/firestore")
async def get_firestore_logs(limit: int = 100):
    """Get recent order logs from Firestore (persistent storage)"""
    if not db:
        return {
            "status": "error",
            "message": "Firestore not available",
            "logs": []
        }
    
    try:
        logs = []
        query = db.collection('webhook_orders').order_by('timestamp', direction=firestore.Query.DESCENDING).limit(limit)
        docs = query.stream()
        
        for doc in docs:
            log_entry = doc.to_dict()
            # Convert Firestore timestamp to ISO format
            if 'timestamp' in log_entry:
                log_entry['timestamp'] = log_entry['timestamp'].isoformat()
            logs.append(log_entry)
        
        return {
            "status": "success",
            "count": len(logs),
            "logs": logs,
            "source": "firestore",
            "note": "These logs are persisted across container restarts"
        }
    except Exception as e:
        logger.error(f"❌ Error reading Firestore logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading logs: {str(e)}"
        )
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
            try:
                should_queue, reason, _ = should_queue_signal("PRE_OPEN")
            except Exception as e:
                logger.warning(f"⚠️  Queue processor: Error checking market status: {e}, skipping execution check")
                continue
            
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
        
        # Queued signals are executed during AMO window, so always use AMO with PRE_OPEN
        amo_timing = "PRE_OPEN"
        
        # Process order legs
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
                
                # Force CNC (delivery) for equity orders
                product_type_to_use = "CNC" if leg.instrument == "EQ" else leg.productType
                
                # Place AMO order (queued signals always go as AMO with PRE_OPEN)
                logger.info(f"🌙 Executing queued signal as AMO (timing: {amo_timing})")
                order_response = dhan_client.place_order(
                    security_id=security_id,
                    exchange=leg.exchange,
                    transaction_type=leg.transactionType,
                    quantity=int(leg.quantity),
                    order_type=leg.orderType,
                    product_type=product_type_to_use,  # Force CNC for equity
                    price=float(leg.price) if leg.orderType in ["LMT", "LIMIT"] else 0,
                    amo=True,  # Always AMO for queued signals
                    amo_time=amo_timing  # PRE_OPEN
                )
                
                results.append(order_response)
        
        # Mark as executed
        execution_result = {
            "signal_id": signal_id,
            "status": "executed",
            "results": results,
            "timestamp": datetime.now(IST).isoformat()
        }
        signal_queue.mark_executed(signal_id, execution_result)
        
        # Send consolidated Telegram notification for queued execution
        telegram = get_notifier()
        if telegram.enabled:
            legs_for_notification = [
                {
                    "symbol": leg.symbol,
                    "transactionType": leg.transactionType,
                    "quantity": leg.quantity,
                    "exchange": leg.exchange
                }
                for leg in payload.order_legs
            ]
            asyncio.create_task(telegram.notify_order_complete(
                legs=legs_for_notification,
                results=results,
                execution_mode="AMO"  # Queued signals always execute as AMO
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
                loop = asyncio.get_running_loop()
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
        
        # =================================================================
        # ORDER ROUTING LOGIC - Based on Market Status
        # =================================================================
        # 1. Market hours (9:15 AM - 3:30 PM) → Execute IMMEDIATELY (no AMO)
        # 2. AMO window (5:00 PM - 8:59 AM next day) → Place AMO with PRE_OPEN
        # 3. Between 3:30 PM - 5:00 PM (Post-market to AMO start) → QUEUE for AMO
        # 4. Weekend/Holiday → QUEUE for next trading day AMO
        # 5. Always use CNC (delivery) for equity orders
        # =================================================================
        
        from trading_calendar import is_market_open, is_amo_window
        
        market_status, market_message = get_market_status()
        is_market_hours = is_market_open()
        is_amo_hours = is_amo_window()
        
        logger.info(f"🏛️  Market Status: {market_status} - {market_message}")
        logger.info(f"📊 Market Open: {is_market_hours}, AMO Window: {is_amo_hours}")
        
        # Determine order execution mode
        # Default AMO timing is PRE_OPEN per user requirement
        amo_timing = "PRE_OPEN"  # Default: Pre-market open
        execute_immediate = False  # Whether to place regular order (not AMO)
        should_queue_order = False  # Whether to queue for later
        queue_reason = ""
        
        if is_market_hours:
            # CASE 1: Market is open → Execute immediately (regular order, no AMO)
            execute_immediate = True
            logger.info("🟢 Market is OPEN - Executing order IMMEDIATELY (regular order)")
        elif is_amo_hours:
            # CASE 2: AMO window → Place AMO order with PRE_OPEN
            execute_immediate = False  # AMO mode
            logger.info(f"🌙 AMO window active - Placing AMO order (timing: {amo_timing})")
        elif market_status in ["WEEKEND", "HOLIDAY"]:
            # CASE 3: Weekend/Holiday → Queue for next trading day AMO
            should_queue_order = True
            queue_reason = f"Non-trading day ({market_status})"
            logger.info(f"📅 {market_status} - Queueing order for next trading day AMO")
        else:
            # CASE 4: Post-market to AMO start (3:30 PM - 5:00 PM) → Queue
            # This is the gap period where neither market nor AMO is active
            should_queue_order = True
            queue_reason = "Post-market period (3:30 PM - 5:00 PM) - AMO not yet accepting"
            logger.info(f"⏳ {queue_reason} - Queueing order")
        
        # Handle queueing if needed
        if should_queue_order:
            next_trading_date = get_next_trading_day()
            # Calculate AMO scheduled time (when AMO window opens at 5 PM)
            from zoneinfo import ZoneInfo
            scheduled_time = datetime.combine(
                datetime.now(IST).date(), 
                datetime.min.time()
            ).replace(hour=17, minute=0, second=0, tzinfo=ZoneInfo("Asia/Kolkata"))
            
            # If it's already past 5 PM today, queue for next trading day
            if datetime.now(IST) >= scheduled_time or market_status in ["WEEKEND", "HOLIDAY"]:
                scheduled_time = datetime.combine(
                    next_trading_date,
                    datetime.min.time()
                ).replace(hour=17, minute=0, second=0, tzinfo=ZoneInfo("Asia/Kolkata"))
            
            signal_id = signal_queue.add_signal(
                payload=payload_dict,
                scheduled_time=scheduled_time,
                reason=queue_reason
            )
            
            logger.info(
                f"📥 Signal queued: ID={signal_id}, "
                f"reason={queue_reason}, "
                f"scheduled={scheduled_time.strftime('%Y-%m-%d %H:%M IST')}"
            )
            
            # Send Telegram notification for queued signal
            telegram = get_notifier()
            if telegram.enabled:
                legs_for_notification = [
                    {
                        "symbol": leg.symbol,
                        "transactionType": leg.transactionType,
                        "quantity": leg.quantity,
                        "exchange": leg.exchange
                    }
                    for leg in payload.order_legs
                ]
                asyncio.create_task(telegram.notify_queued(
                    legs=legs_for_notification,
                    scheduled_time=scheduled_time
                ))
            
            return {
                "status": "queued",
                "signal_id": signal_id,
                "reason": queue_reason,
                "scheduled_time": scheduled_time.isoformat(),
                "message": f"Signal queued for execution: {queue_reason}"
            }
        
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
                        
                        # Log to Firestore (persistent)
                        log_order_to_firestore(
                            alert_type=payload.alertType,
                            leg_number=idx,
                            leg=leg,
                            status="failed",
                            message=result["message"],
                            source_ip=source_ip
                        )
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
                                
                                # Log to Firestore (persistent)
                                log_order_to_firestore(
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
                        
                        # =================================================================
                        # PLACE ORDER - Based on execution mode
                        # =================================================================
                        # execute_immediate=True → Regular order (during market hours)
                        # execute_immediate=False → AMO order (during AMO window)
                        # =================================================================
                        
                        # Force CNC (delivery) for equity orders
                        product_type_to_use = "CNC" if leg.instrument == "EQ" else leg.productType
                        
                        if execute_immediate:
                            # IMMEDIATE EXECUTION - Regular order during market hours
                            logger.info(f"🚀 Placing IMMEDIATE order (market is open)")
                            use_amo = False
                            use_amo_time = None
                        else:
                            # AMO ORDER - During AMO window
                            logger.info(f"🌙 Placing AMO order (timing: {amo_timing})")
                            use_amo = True
                            use_amo_time = amo_timing  # PRE_OPEN (set earlier)
                        
                        # Use worker process for order placement (offload API call)
                        if executor:
                            loop = asyncio.get_running_loop()
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
                                product_type_to_use,  # Force CNC for equity
                                float(leg.price) if leg.orderType in ["LMT", "LIMIT"] else 0,
                                0,  # trigger_price
                                use_amo,  # True for AMO, False for immediate
                                use_amo_time if use_amo else "OPEN"  # AMO timing
                            )
                        else:
                            # Fallback to synchronous call if executor not available
                            order_response = dhan_client.place_order(
                                security_id=security_id,
                                exchange=leg.exchange,
                                transaction_type=leg.transactionType,
                                quantity=int(leg.quantity),
                                order_type=leg.orderType,
                                product_type=product_type_to_use,  # Force CNC for equity
                                price=float(leg.price) if leg.orderType in ["LMT", "LIMIT"] else 0,
                                amo=use_amo,  # True for AMO, False for immediate
                                amo_time=use_amo_time if use_amo else "OPEN",
                                tag=f"TV-{payload.alertType}-{idx}"
                            )
                        
                        # Build result with execution mode info
                        execution_mode = "IMMEDIATE" if execute_immediate else f"AMO ({amo_timing})"
                        result = {
                            "leg_number": idx,
                            "symbol": leg.symbol,
                            "transaction": leg.transactionType,
                            "quantity": leg.quantity,
                            "execution_mode": execution_mode,
                            "product_type": product_type_to_use,
                            "status": order_response["status"],
                            "message": order_response["message"],
                            "order_id": order_response.get("order_id")
                        }
                        
                        if result["status"] == "success":
                            if execute_immediate:
                                logger.info(f"✅ Order placed IMMEDIATELY: {result['order_id']}")
                            else:
                                logger.info(f"✅ AMO Order placed: {result['order_id']} (executes at {amo_timing})")
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
                        
                        # Log to Firestore (persistent)
                        log_order_to_firestore(
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
                    
                    # Log to Firestore (persistent)
                    log_order_to_firestore(
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
                
            results.append(result)
        
        # Send consolidated Telegram notification
        if telegram.enabled:
            # Prepare legs summary for notification
            legs_for_notification = [
                {
                    "symbol": leg.symbol,
                    "transactionType": leg.transactionType,
                    "quantity": leg.quantity,
                    "exchange": leg.exchange
                }
                for leg in payload.order_legs
            ]
            # Determine execution mode
            exec_mode = "IMMEDIATE" if execute_immediate else "AMO"
            asyncio.create_task(telegram.notify_order_complete(
                legs=legs_for_notification,
                results=results,
                execution_mode=exec_mode
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
