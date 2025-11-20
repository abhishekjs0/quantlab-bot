#!/usr/bin/env python3
"""
FastAPI Webhook Server for TradingView Alerts
Accepts POST requests with JSON payloads for multi-leg order execution
"""

import os
import logging
import json
import csv
from datetime import datetime
from typing import Optional
from pathlib import Path
from pydantic import BaseModel, Field, field_validator
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
import uvicorn

# Import Dhan broker
try:
    from dhan_broker import DhanBroker
    DHAN_AVAILABLE = True
except ImportError:
    DHAN_AVAILABLE = False
    logging.warning("Dhan broker module not available. Orders will be logged only.")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('webhook_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# CSV logging setup
CSV_LOG_FILE = 'webhook_orders.csv'
CSV_FIELDNAMES = ['timestamp', 'alert_type', 'symbol', 'exchange', 'transaction', 'quantity', 
                  'order_type', 'product_type', 'price', 'status', 'order_id', 'message']

# Create CSV file with headers if it doesn't exist
if not Path(CSV_LOG_FILE).exists():
    with open(CSV_LOG_FILE, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()

def log_order_to_csv(order_data: dict):
    """Log order details to CSV file"""
    try:
        with open(CSV_LOG_FILE, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
            writer.writerow(order_data)
    except Exception as e:
        logger.error(f"Failed to write to CSV: {e}")

# Load environment from main .env file
from dotenv import load_dotenv
load_dotenv('.env')

# Environment configuration
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "GTcl4")
PORT = int(os.getenv("WEBHOOK_PORT", "80"))
HOST = os.getenv("WEBHOOK_HOST", "0.0.0.0")
ENABLE_DHAN = os.getenv("ENABLE_DHAN", "false").lower() == "true"

# Initialize Dhan broker if enabled
dhan_broker = None
if ENABLE_DHAN and DHAN_AVAILABLE:
    try:
        dhan_broker = DhanBroker()
        logger.info("Dhan broker initialized and ready for order execution")
    except Exception as e:
        logger.error(f"Failed to initialize Dhan broker: {e}")
        logger.warning("Orders will be logged only, not executed")
else:
    logger.info("Dhan execution disabled. Orders will be logged only.")

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
    title="TradingView Webhook Server",
    description="Webhook endpoint for receiving TradingView alerts and executing trades",
    version="1.0.0"
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "running",
        "service": "TradingView Webhook Server",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
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
        # Read raw body
        body = await request.body()
        body_str = body.decode('utf-8')
        
        logger.info(f"Received webhook request from {request.client.host}")
        logger.debug(f"Raw body: {body_str}")
        
        # Parse JSON from raw body
        import json
        try:
            payload_dict = json.loads(body_str)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON payload: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid JSON format: {str(e)}"
            )
        
        # Validate payload structure
        try:
            payload = WebhookPayload(**payload_dict)
        except Exception as e:
            logger.error(f"Payload validation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Payload validation error: {str(e)}"
            )
        
        # Verify secret
        if payload.secret != WEBHOOK_SECRET:
            logger.warning(f"Invalid secret received from {request.client.host}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook secret"
            )
        
        # Log received alert
        logger.info(f"Valid webhook received: {payload.alertType} with {len(payload.order_legs)} leg(s)")
        
        # Process each order leg
        results = []
        for idx, leg in enumerate(payload.order_legs, 1):
            logger.info(
                f"Order Leg {idx}/{len(payload.order_legs)}: "
                f"{leg.transactionType} {leg.quantity} {leg.symbol} "
                f"@ {leg.exchange} ({leg.orderType})"
            )
            
            # Execute order with Dhan if enabled
            if dhan_broker:
                try:
                    # Get security ID for the symbol
                    security_id = dhan_broker.get_security_id(leg.symbol, leg.exchange)
                    
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
                    else:
                        # Place order with Dhan
                        order_response = dhan_broker.place_order(
                            security_id=security_id,
                            exchange=leg.exchange,
                            transaction_type=leg.transactionType,
                            quantity=int(leg.quantity),
                            order_type=leg.orderType,
                            product_type=leg.productType,
                            price=float(leg.price) if leg.orderType in ["LMT", "LIMIT"] else 0,
                            amo=True,  # Enable AMO for after-market orders
                            amo_time="OPEN_30",  # Pump 30 minutes after market open
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
                        
                        logger.info(f"Dhan order result: {result}")
                        
                        # Log to CSV
                        log_order_to_csv({
                            'timestamp': datetime.utcnow().isoformat(),
                            'alert_type': payload.alertType,
                            'symbol': leg.symbol,
                            'exchange': leg.exchange,
                            'transaction': leg.transactionType,
                            'quantity': leg.quantity,
                            'order_type': leg.orderType,
                            'product_type': leg.productType,
                            'price': leg.price,
                            'status': result['status'],
                            'order_id': result.get('order_id', ''),
                            'message': result['message']
                        })
                        
                except Exception as e:
                    logger.error(f"Error executing order leg {idx}: {e}", exc_info=True)
                    result = {
                        "leg_number": idx,
                        "symbol": leg.symbol,
                        "transaction": leg.transactionType,
                        "quantity": leg.quantity,
                        "status": "error",
                        "message": str(e),
                        "order_id": None
                    }
            else:
                # Dhan not enabled, just acknowledge
                result = {
                    "leg_number": idx,
                    "symbol": leg.symbol,
                    "transaction": leg.transactionType,
                    "quantity": leg.quantity,
                    "status": "acknowledged",
                    "message": "Order received and logged (Dhan execution disabled)",
                    "order_id": None
                }
                
                # Log to CSV even in test mode
                log_order_to_csv({
                    'timestamp': datetime.utcnow().isoformat(),
                    'alert_type': payload.alertType,
                    'symbol': leg.symbol,
                    'exchange': leg.exchange,
                    'transaction': leg.transactionType,
                    'quantity': leg.quantity,
                    'order_type': leg.orderType,
                    'product_type': leg.productType,
                    'price': leg.price,
                    'status': 'test_mode',
                    'order_id': '',
                    'message': 'Test mode - order not executed'
                })
            
            results.append(result)
        
        response = {
            "status": "success",
            "message": f"Processed {len(payload.order_legs)} order leg(s)",
            "alertType": payload.alertType,
            "timestamp": datetime.utcnow().isoformat(),
            "results": results
        }
        
        logger.info(f"Webhook processed successfully: {response}")
        return JSONResponse(content=response, status_code=status.HTTP_200_OK)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing webhook: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@app.post("/webhook/test")
async def test_webhook(payload: WebhookPayload):
    """
    Test endpoint with automatic JSON parsing (for testing with tools like Postman)
    """
    if payload.secret != WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook secret"
        )
    
    return {
        "status": "success",
        "message": "Test payload received",
        "alertType": payload.alertType,
        "order_legs_count": len(payload.order_legs),
        "timestamp": datetime.utcnow().isoformat()
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "message": "Internal server error",
            "timestamp": datetime.utcnow().isoformat()
        }
    )


def main():
    """Start the webhook server"""
    logger.info(f"Starting webhook server on {HOST}:{PORT}")
    logger.info(f"Webhook endpoint: http://{HOST}:{PORT}/webhook")
    logger.info(f"Health check: http://{HOST}:{PORT}/health")
    
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="info",
        access_log=True
    )


if __name__ == "__main__":
    main()
