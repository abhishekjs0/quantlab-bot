#!/usr/bin/env python3
"""
Dhan API Client for Order Execution
Lightweight wrapper around dhanhq library
"""

import os
import logging
import csv
from typing import Optional, Dict, Any
from dhanhq import dhanhq

logger = logging.getLogger(__name__)


class DhanClient:
    """
    Simplified Dhan broker API client for webhook order execution
    """
    
    # Exchange segment mappings
    EXCHANGE_MAP = {
        "NSE": "NSE_EQ",
        "NSE_EQ": "NSE_EQ",
        "BSE": "BSE_EQ",
        "BSE_EQ": "BSE_EQ",
        "NFO": "NSE_FNO",
        "NSE_FNO": "NSE_FNO",
        "BFO": "BSE_FNO",
        "BSE_FNO": "BSE_FNO",
        "MCX": "MCX_COMM",
        "MCX_COMM": "MCX_COMM"
    }
    
    # Transaction type mappings
    TRANSACTION_MAP = {
        "B": "BUY",
        "BUY": "BUY",
        "S": "SELL",
        "SELL": "SELL"
    }
    
    # Order type mappings
    ORDER_TYPE_MAP = {
        "MKT": "MARKET",
        "MARKET": "MARKET",
        "LMT": "LIMIT",
        "LIMIT": "LIMIT",
        "SL": "STOP_LOSS",
        "STOP_LOSS": "STOP_LOSS",
        "SL-M": "STOP_LOSS_MARKET",
        "STOP_LOSS_MARKET": "STOP_LOSS_MARKET"
    }
    
    # Product type mappings
    PRODUCT_MAP = {
        "C": "CNC",
        "CNC": "CNC",
        "I": "INTRADAY",
        "INTRA": "INTRADAY",
        "INTRADAY": "INTRADAY",
        "M": "MARGIN",
        "MARGIN": "MARGIN"
    }
    
    # AMO time mappings
    AMO_TIME_MAP = {
        "PRE_OPEN": "PRE_OPEN",
        "OPEN": "OPEN",
        "OPEN_30": "OPEN_30",
        "OPEN_60": "OPEN_60"
    }
    
    def __init__(self, client_id: Optional[str] = None, access_token: Optional[str] = None):
        """
        Initialize Dhan client
        
        Args:
            client_id: Dhan client ID (defaults to env DHAN_CLIENT_ID)
            access_token: Dhan access token (defaults to env DHAN_ACCESS_TOKEN)
        """
        self.client_id = client_id or os.getenv("DHAN_CLIENT_ID")
        self.access_token = access_token or os.getenv("DHAN_ACCESS_TOKEN")
        
        if not self.client_id or not self.access_token:
            raise ValueError(
                "Dhan credentials not provided. Set DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN "
                "environment variables."
            )
        
        # Load security ID mapping
        self.security_map = self._load_security_map()
        
        # Initialize Dhan client
        try:
            self.dhan = dhanhq(self.client_id, self.access_token)
            logger.info("Dhan client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Dhan client: {e}")
            raise
    
    def _load_security_map(self) -> Dict[str, int]:
        """Load symbol to security_id mapping from CSV"""
        security_map = {}
        csv_path = os.path.join(os.path.dirname(__file__), "security_id_list.csv")
        
        if not os.path.exists(csv_path):
            logger.warning(f"Security ID list not found at {csv_path}")
            return security_map
        
        try:
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    symbol = row.get('SM_SYMBOL_NAME', '').strip()
                    exchange = row.get('SEM_EXM_EXCH_ID', '').strip()
                    security_id = row.get('SEM_SMST_SECURITY_ID', '').strip()
                    
                    if symbol and security_id:
                        key = f"{symbol}_{exchange}"
                        try:
                            security_map[key] = int(security_id)
                        except ValueError:
                            continue
            
            logger.info(f"Loaded {len(security_map)} security IDs from CSV")
        except Exception as e:
            logger.error(f"Error loading security ID list: {e}")
        
        return security_map
    
    def get_security_id(self, symbol: str, exchange: str) -> Optional[int]:
        """
        Get security ID for a symbol and exchange
        
        Args:
            symbol: Trading symbol (e.g., 'RELIANCE')
            exchange: Exchange code (e.g., 'NSE')
            
        Returns:
            Security ID as integer, or None if not found
        """
        key = f"{symbol}_{exchange}"
        security_id = self.security_map.get(key)
        
        if not security_id:
            logger.warning(f"Security ID not found for {symbol} on {exchange}")
        
        return security_id
    
    def place_order(
        self,
        security_id: int,
        exchange: str,
        transaction_type: str,
        quantity: int,
        order_type: str = "MARKET",
        product_type: str = "CNC",
        price: float = 0.0,
        trigger_price: float = 0.0,
        disclosed_quantity: int = 0,
        validity: str = "DAY",
        amo: bool = False,
        amo_time: str = "OPEN",
        tag: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Place an order with Dhan
        
        Args:
            security_id: Dhan security ID
            exchange: Exchange segment
            transaction_type: BUY or SELL
            quantity: Number of shares/contracts
            order_type: MARKET, LIMIT, STOP_LOSS, STOP_LOSS_MARKET
            product_type: CNC, INTRADAY, MARGIN
            price: Limit price (for LIMIT orders)
            trigger_price: Trigger price (for STOP_LOSS orders)
            disclosed_quantity: Disclosed quantity for iceberg orders
            validity: DAY or IOC
            amo: After Market Order flag
            amo_time: AMO timing (PRE_OPEN, OPEN, OPEN_30, OPEN_60)
            tag: Custom order tag
            
        Returns:
            Dict with status, message, order_id
        """
        try:
            # Map parameters
            exchange_segment = self.EXCHANGE_MAP.get(exchange, exchange)
            transaction = self.TRANSACTION_MAP.get(transaction_type, transaction_type)
            order_t = self.ORDER_TYPE_MAP.get(order_type, order_type)
            product = self.PRODUCT_MAP.get(product_type, product_type)
            amo_timing = self.AMO_TIME_MAP.get(amo_time, "OPEN") if amo else None
            
            # Build order parameters
            order_params = {
                "security_id": str(security_id),
                "exchange_segment": exchange_segment,
                "transaction_type": transaction,
                "quantity": quantity,
                "order_type": order_t,
                "product_type": product,
                "price": price,
                "validity": validity
            }
            
            # Add optional parameters
            if trigger_price > 0:
                order_params["trigger_price"] = trigger_price
            
            if disclosed_quantity > 0:
                order_params["disclosed_quantity"] = disclosed_quantity
            
            if amo and amo_timing:
                order_params["after_market_order"] = True
                order_params["amo_time"] = amo_timing
            
            if tag:
                order_params["tag"] = tag
            
            logger.info(f"Placing order: {transaction} {quantity} {security_id} @ {exchange_segment}")
            
            # Place order
            response = self.dhan.place_order(**order_params)
            
            if response.get('status') == 'success':
                order_id = response.get('data', {}).get('orderId')
                return {
                    "status": "success",
                    "message": "Order placed successfully",
                    "order_id": order_id,
                    "response": response
                }
            else:
                error_msg = response.get('remarks', 'Unknown error')
                return {
                    "status": "failed",
                    "message": error_msg,
                    "order_id": None,
                    "response": response
                }
        
        except Exception as e:
            logger.error(f"Error placing order: {e}", exc_info=True)
            return {
                "status": "error",
                "message": str(e),
                "order_id": None
            }
    
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Get status of an order
        
        Args:
            order_id: Dhan order ID
            
        Returns:
            Order status details
        """
        try:
            response = self.dhan.get_order_by_id(order_id)
            return response
        except Exception as e:
            logger.error(f"Error fetching order status: {e}")
            return {"status": "error", "message": str(e)}
    
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel an order
        
        Args:
            order_id: Dhan order ID
            
        Returns:
            Cancellation response
        """
        try:
            response = self.dhan.cancel_order(order_id)
            return response
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return {"status": "error", "message": str(e)}
