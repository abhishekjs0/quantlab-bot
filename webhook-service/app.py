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
from typing import Optional
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

# Background health check task
async def periodic_health_check():
    """Periodically check Dhan token validity and log status"""
    while True:
        try:
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
            if not ENABLE_DHAN or not dhan_auth:
                continue
                
            # Check token validity
            token = dhan_auth.get_valid_token(auto_refresh=False)
            if token:
                logger.info("✅ Periodic health check: Dhan token is valid")
            else:
                logger.warning("⚠️  Periodic health check: Dhan token expired, will auto-refresh on next order")
                
        except Exception as e:
            logger.error(f"❌ Health check error: {e}")

# Initialize Dhan authentication and client
dhan_auth = None
dhan_client = None

if ENABLE_DHAN:
    try:
        # Initialize authentication module with auto-refresh
        dhan_auth = load_auth_from_env()
        if not dhan_auth:
            logger.error("❌ Failed to load Dhan authentication from environment")
            logger.warning("Orders will be logged only, not executed")
        else:
            # Get a valid token (will auto-generate if needed)
            access_token = dhan_auth.get_valid_token()
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


# FastAPI application
app = FastAPI(
    title="TradingView Webhook Service",
    description="Cloud-deployed webhook endpoint for TradingView alerts → Dhan AMO order execution",
    version="2.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

@app.on_event("startup")
async def startup_event():
    """Start background tasks on application startup"""
    if AUTO_HEALTH_CHECK and ENABLE_DHAN:
        asyncio.create_task(periodic_health_check())
        logger.info(f"🔄 Auto health check enabled (interval: {HEALTH_CHECK_INTERVAL}s)")


@app.get("/")
async def root():
    """Root endpoint - service info"""
    return {
        "service": "TradingView Webhook Service",
        "version": "2.1.0",
        "status": "running",
        "endpoints": {
            "webhook": "/webhook",
            "health": "/health",
            "ready": "/ready",
            "logs": "/logs",
            "docs": "/docs"
        },
        "config": {
            "dhan_enabled": ENABLE_DHAN,
            "auto_health_check": AUTO_HEALTH_CHECK,
            "health_check_interval": f"{HEALTH_CHECK_INTERVAL}s (6 hours)",
            "csv_logging": True,
            "amo_mode": "OPEN_30"  # All orders are AMO for next day
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
                token = dhan_auth.get_valid_token(auto_refresh=False)
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
        
        # Validate payload structure
        try:
            payload = WebhookPayload(**payload_dict)
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
                        access_token = dhan_auth.get_valid_token()
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
                        # Place AMO order for next day execution (always AMO mode)
                        logger.info(f"🌙 Placing AMO order for next day execution")
                        order_response = dhan_client.place_order(
                            security_id=security_id,
                            exchange=leg.exchange,
                            transaction_type=leg.transactionType,
                            quantity=int(leg.quantity),
                            order_type=leg.orderType,
                            product_type=leg.productType,
                            price=float(leg.price) if leg.orderType in ["LMT", "LIMIT"] else 0,
                            amo=True,  # Always AMO
                            amo_time="OPEN_30",  # Execute at market open + 30 mins
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
