#!/usr/bin/env python3
"""
Dhan Broker Integration Module
Handles order placement with DhanHQ API
"""

import os
import logging
from typing import Optional, Dict, Any
from dhanhq import dhanhq

logger = logging.getLogger(__name__)


class DhanBroker:
    """
    Dhan broker API wrapper for order execution
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
        "MARGIN": "MARGIN",
        "MTF": "MTF",
        "CO": "CO",
        "BO": "BO"
    }
    
    # AMO time mappings
    AMO_TIME_MAP = {
        "PRE_OPEN": "PRE_OPEN",
        "OPEN": "OPEN",
        "OPEN_30": "OPEN_30",  # 30 minutes after market open
        "OPEN_60": "OPEN_60"   # 60 minutes after market open
    }
    
    def __init__(self, client_id: Optional[str] = None, access_token: Optional[str] = None):
        """
        Initialize Dhan broker connection
        
        Args:
            client_id: Dhan client ID (defaults to env DHAN_CLIENT_ID)
            access_token: Dhan access token (defaults to env DHAN_ACCESS_TOKEN)
        """
        self.client_id = client_id or os.getenv("DHAN_CLIENT_ID")
        self.access_token = access_token or os.getenv("DHAN_ACCESS_TOKEN")
        
        if not self.client_id or not self.access_token:
            raise ValueError(
                "Dhan credentials not provided. Set DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN "
                "environment variables or pass them to constructor."
            )
        
        # Initialize Dhan client
        try:
            self.dhan = dhanhq(self.client_id, self.access_token)
            logger.info("Dhan broker initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Dhan broker: {e}")
            raise
    
    def _map_exchange_for_lookup(self, exchange: str) -> str:
        """Map exchange code for security master lookup (uses simple codes)"""
        # For security master lookup, use simple exchange codes
        exchange_upper = exchange.upper()
        
        # Map common formats to simple codes
        if exchange_upper in ["NSE", "NSE_EQ"]:
            return "NSE"
        elif exchange_upper in ["BSE", "BSE_EQ"]:
            return "BSE"
        elif exchange_upper in ["NFO", "NSE_FNO"]:
            return "NSE"
        elif exchange_upper in ["MCX", "MCX_COMM"]:
            return "MCX"
        else:
            logger.warning(f"Unknown exchange '{exchange}', using as-is")
            return exchange_upper
    
    def _map_exchange_for_order(self, exchange: str) -> str:
        """Map exchange code for order placement (uses segment codes)"""
        mapped = self.EXCHANGE_MAP.get(exchange.upper())
        if not mapped:
            logger.warning(f"Unknown exchange '{exchange}', using as-is")
            return exchange
        return mapped
    
    def _map_transaction_type(self, transaction_type: str) -> str:
        """Map transaction type to Dhan format"""
        mapped = self.TRANSACTION_MAP.get(transaction_type.upper())
        if not mapped:
            logger.warning(f"Unknown transaction type '{transaction_type}', defaulting to BUY")
            return "BUY"
        return mapped
    
    def _map_order_type(self, order_type: str) -> str:
        """Map order type to Dhan format"""
        mapped = self.ORDER_TYPE_MAP.get(order_type.upper())
        if not mapped:
            logger.warning(f"Unknown order type '{order_type}', defaulting to MARKET")
            return "MARKET"
        return mapped
    
    def _map_product_type(self, product_type: str) -> str:
        """Map product type to Dhan format"""
        mapped = self.PRODUCT_MAP.get(product_type.upper())
        if not mapped:
            logger.warning(f"Unknown product type '{product_type}', defaulting to INTRADAY")
            return "INTRADAY"
        return mapped
    
    def get_security_id(self, symbol: str, exchange: str) -> Optional[str]:
        """
        Get Dhan security ID for a symbol
        
        Args:
            symbol: Trading symbol
            exchange: Exchange code
            
        Returns:
            Security ID string or None if not found
        """
        try:
            # Fetch security master list as DataFrame
            df = self.dhan.fetch_security_list("compact")
            
            if df is None or df.empty:
                logger.error("Failed to fetch security list from Dhan")
                return None
            
            # Map exchange to Dhan format for lookup
            exchange_mapped = self._map_exchange_for_lookup(exchange)
            
            # Filter for the symbol and exchange
            filtered = df[
                (df["SEM_TRADING_SYMBOL"] == symbol) & 
                (df["SEM_EXM_EXCH_ID"] == exchange_mapped)
            ]
            
            if not filtered.empty:
                sec_id = filtered.iloc[0]["SEM_SMST_SECURITY_ID"]
                logger.info(f"Found security ID {sec_id} for {symbol} on {exchange}")
                return str(int(sec_id))
            
            logger.warning(f"Security ID not found for {symbol} on {exchange}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching security ID: {e}")
            return None
    
    def get_ltp(self, security_id: str, exchange: str) -> Optional[float]:
        """
        Get Last Traded Price (LTP) for a security
        
        Args:
            security_id: Dhan security ID
            exchange: Exchange code
            
        Returns:
            LTP as float or None if not found
        """
        try:
            exchange_seg = self._map_exchange_for_order(exchange)
            
            # Use ticker_data API to get LTP
            quote = self.dhan.ticker_data(
                securities={exchange_seg: [security_id]}
            )
            
            if quote and quote.get("status") == "success":
                data_dict = quote.get("data", {})
                if isinstance(data_dict, dict):
                    data = data_dict.get(exchange_seg, [])
                    if data and len(data) > 0:
                        ltp = data[0].get("last_price") or data[0].get("LTP")
                        if ltp:
                            logger.info(f"LTP for {security_id} on {exchange}: {ltp}")
                            return float(ltp)
            
            logger.warning(f"LTP not found for {security_id} on {exchange}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching LTP: {e}")
            return None
    
    def place_order(
        self,
        security_id: str,
        exchange: str,
        transaction_type: str,
        quantity: int,
        order_type: str,
        product_type: str,
        price: float = 0,
        trigger_price: float = 0,
        disclosed_quantity: int = 0,
        validity: str = "DAY",
        amo: bool = False,
        amo_time: str = "OPEN_30",
        tag: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Place regular order with Dhan
        
        Args:
            security_id: Dhan security ID
            exchange: Exchange segment
            transaction_type: BUY or SELL
            quantity: Order quantity
            order_type: MARKET, LIMIT, STOP_LOSS, STOP_LOSS_MARKET
            product_type: CNC, INTRADAY, MARGIN, etc.
            price: Limit price (required for LIMIT orders)
            trigger_price: Trigger price (required for STOP_LOSS orders)
            disclosed_quantity: Disclosed quantity for icebergs
            validity: Order validity (DAY, IOC)
            amo: After market order flag
            amo_time: AMO pump time (PRE_OPEN, OPEN, OPEN_30, OPEN_60)
            tag: Optional correlation tag
            
        Returns:
            Dict with order response including order_id and status
        """
        try:
            # Map parameters to Dhan format
            exchange_seg = self._map_exchange_for_order(exchange)
            trans_type = self._map_transaction_type(transaction_type)
            ord_type = self._map_order_type(order_type)
            prod_type = self._map_product_type(product_type)
            
            logger.info(
                f"Placing order: {trans_type} {quantity} {security_id} @ {exchange_seg} "
                f"({ord_type}, {prod_type})"
            )
            
            # Build order payload based on Dhan API requirements
            order_params = {
                "security_id": security_id,
                "exchange_segment": exchange_seg,
                "transaction_type": getattr(self.dhan, trans_type),
                "quantity": quantity,
                "order_type": getattr(self.dhan, ord_type),
                "product_type": getattr(self.dhan, prod_type),
                "price": price if ord_type in ["LIMIT", "STOP_LOSS"] else 0,
            }
            
            # Add trigger price for stop loss orders
            if ord_type in ["STOP_LOSS", "STOP_LOSS_MARKET"]:
                order_params["trigger_price"] = trigger_price
            
            # Add optional parameters
            if disclosed_quantity > 0:
                order_params["disclosed_quantity"] = disclosed_quantity
            
            if validity:
                order_params["validity"] = validity
            
            if amo:
                order_params["after_market_order"] = True
                # Set AMO time (default OPEN_30 for 30 minutes after market open)
                order_params["amo_time"] = self.AMO_TIME_MAP.get(amo_time.upper(), "OPEN_30")
            
            if tag:
                order_params["tag"] = tag
            
            # Place order
            response = self.dhan.place_order(**order_params)
            
            if response and response.get("status") == "success":
                order_id = response.get("data", {}).get("orderId")
                logger.info(f"Order placed successfully. Order ID: {order_id}")
                return {
                    "status": "success",
                    "order_id": order_id,
                    "message": "Order placed successfully",
                    "raw_response": response
                }
            else:
                error_msg = response.get("remarks", "Unknown error") if response else "No response from broker"
                logger.error(f"Order placement failed: {error_msg}")
                return {
                    "status": "failed",
                    "order_id": None,
                    "message": error_msg,
                    "raw_response": response
                }
                
        except Exception as e:
            logger.error(f"Exception placing order: {e}", exc_info=True)
            return {
                "status": "error",
                "order_id": None,
                "message": str(e),
                "raw_response": None
            }
    
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Get order status by ID
        
        Args:
            order_id: Dhan order ID
            
        Returns:
            Dict with order details
        """
        try:
            response = self.dhan.get_order_by_id(order_id)
            return {
                "status": "success",
                "data": response
            }
        except Exception as e:
            logger.error(f"Error fetching order status: {e}")
            return {
                "status": "error",
                "message": str(e),
                "data": None
            }
    
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel an order
        
        Args:
            order_id: Dhan order ID
            
        Returns:
            Dict with cancellation response
        """
        try:
            response = self.dhan.cancel_order(order_id)
            if response and response.get("status") == "success":
                logger.info(f"Order {order_id} cancelled successfully")
                return {
                    "status": "success",
                    "message": "Order cancelled successfully",
                    "raw_response": response
                }
            else:
                error_msg = response.get("remarks", "Unknown error") if response else "No response from broker"
                logger.error(f"Order cancellation failed: {error_msg}")
                return {
                    "status": "failed",
                    "message": error_msg,
                    "raw_response": response
                }
        except Exception as e:
            logger.error(f"Exception cancelling order: {e}")
            return {
                "status": "error",
                "message": str(e),
                "raw_response": None
            }
    
    def get_positions(self) -> Dict[str, Any]:
        """Get current positions"""
        try:
            response = self.dhan.get_positions()
            return {
                "status": "success",
                "data": response
            }
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return {
                "status": "error",
                "message": str(e),
                "data": None
            }
    
    def get_fund_limits(self) -> Dict[str, Any]:
        """Get fund limits"""
        try:
            response = self.dhan.get_fund_limits()
            return {
                "status": "success",
                "data": response
            }
        except Exception as e:
            logger.error(f"Error fetching fund limits: {e}")
            return {
                "status": "error",
                "message": str(e),
                "data": None
            }
    
    def place_super_order(
        self,
        security_id: str,
        exchange: str,
        transaction_type: str,
        quantity: int,
        order_type: str,
        product_type: str,
        price: float,
        target_price: float,
        stop_loss_price: float,
        trailing_jump: float = 0,
        tag: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Place Super Order (entry + target + stop loss in one order)
        
        Args:
            security_id: Dhan security ID
            exchange: Exchange segment
            transaction_type: BUY or SELL
            quantity: Order quantity
            order_type: MARKET or LIMIT
            product_type: CNC, INTRADAY, MARGIN, MTF
            price: Entry price
            target_price: Target price for profit
            stop_loss_price: Stop loss price
            trailing_jump: Trailing stop loss jump (0 = no trailing)
            tag: Optional correlation tag
            
        Returns:
            Dict with order response including order_id and status
        """
        try:
            exchange_seg = self._map_exchange_for_order(exchange)
            trans_type = self._map_transaction_type(transaction_type)
            ord_type = self._map_order_type(order_type)
            prod_type = self._map_product_type(product_type)
            
            logger.info(
                f"Placing Super Order: {trans_type} {quantity} {security_id} @ {exchange_seg} "
                f"(Entry: {price}, Target: {target_price}, SL: {stop_loss_price})"
            )
            
            # Build super order payload
            order_params = {
                "dhanClientId": self.client_id,
                "transactionType": getattr(self.dhan, trans_type),
                "exchangeSegment": getattr(self.dhan, exchange_seg),
                "productType": getattr(self.dhan, prod_type),
                "orderType": getattr(self.dhan, ord_type),
                "securityId": security_id,
                "quantity": quantity,
                "price": price,
                "targetPrice": target_price,
                "stopLossPrice": stop_loss_price,
                "trailingJump": trailing_jump
            }
            
            if tag:
                order_params["correlationId"] = tag
            
            # Place super order using direct API call
            response = self.dhan.place_super_order(**order_params)
            
            if response and response.get("status") == "success":
                order_id = response.get("data", {}).get("orderId")
                logger.info(f"Super Order placed successfully. Order ID: {order_id}")
                return {
                    "status": "success",
                    "order_id": order_id,
                    "message": "Super Order placed successfully",
                    "raw_response": response
                }
            else:
                error_msg = response.get("remarks", "Unknown error") if response else "No response from broker"
                logger.error(f"Super Order placement failed: {error_msg}")
                return {
                    "status": "failed",
                    "message": error_msg,
                    "raw_response": response
                }
        except Exception as e:
            logger.error(f"Exception placing Super Order: {e}")
            return {
                "status": "error",
                "message": str(e),
                "raw_response": None
            }
    
    def place_forever_order(
        self,
        security_id: str,
        exchange: str,
        transaction_type: str,
        quantity: int,
        order_type: str,
        product_type: str,
        price: float,
        trigger_price: float,
        order_flag: str = "SINGLE",
        validity: str = "DAY",
        disclosed_quantity: int = 0,
        # OCO parameters (optional)
        price1: Optional[float] = None,
        trigger_price1: Optional[float] = None,
        quantity1: Optional[int] = None,
        tag: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Place Forever Order (Good Till Triggered - GTT order)
        
        Args:
            security_id: Dhan security ID
            exchange: Exchange segment
            transaction_type: BUY or SELL
            quantity: Order quantity
            order_type: MARKET or LIMIT
            product_type: CNC or MTF
            price: Limit price
            trigger_price: Trigger price for GTT
            order_flag: SINGLE (single trigger) or OCO (One Cancels Other)
            validity: Order validity (DAY, IOC)
            disclosed_quantity: Disclosed quantity
            price1: Target price for OCO order (required if order_flag=OCO)
            trigger_price1: Target trigger for OCO (required if order_flag=OCO)
            quantity1: Target quantity for OCO (required if order_flag=OCO)
            tag: Optional correlation tag
            
        Returns:
            Dict with order response including order_id and status
        """
        try:
            exchange_seg = self._map_exchange_for_order(exchange)
            trans_type = self._map_transaction_type(transaction_type)
            ord_type = self._map_order_type(order_type)
            prod_type = self._map_product_type(product_type)
            
            order_flag_upper = order_flag.upper()
            
            logger.info(
                f"Placing Forever Order ({order_flag_upper}): {trans_type} {quantity} {security_id} @ {exchange_seg} "
                f"(Price: {price}, Trigger: {trigger_price})"
            )
            
            # Validate OCO parameters if it's an OCO order
            if order_flag_upper == "OCO":
                if not all([price1, trigger_price1, quantity1]):
                    raise ValueError("OCO orders require price1, trigger_price1, and quantity1")
            
            # Place forever order using Dhan SDK
            response = self.dhan.place_forever(
                security_id=security_id,
                exchange_segment=exchange_seg,  # Use the mapped string directly
                transaction_type=trans_type,    # Use the mapped string directly
                product_type=prod_type,         # Use the mapped string directly
                order_type=ord_type,            # Use the mapped string directly
                quantity=quantity,
                price=price,
                trigger_Price=trigger_price,  # Note: capital P
                order_flag=order_flag_upper,
                disclosed_quantity=disclosed_quantity,
                validity=validity,
                price1=int(price1) if price1 and order_flag_upper == "OCO" else 0,
                trigger_Price1=int(trigger_price1) if trigger_price1 and order_flag_upper == "OCO" else 0,
                quantity1=int(quantity1) if quantity1 and order_flag_upper == "OCO" else 0,
                tag=tag or "",
                symbol=""  # Optional trading symbol
            )
            
            if response and response.get("status") == "success":
                data = response.get("data", {})
                if isinstance(data, dict):
                    order_id = data.get("orderId")
                else:
                    order_id = None
                logger.info(f"Forever Order placed successfully. Order ID: {order_id}")
                return {
                    "status": "success",
                    "order_id": order_id,
                    "message": "Forever Order placed successfully",
                    "raw_response": response
                }
            else:
                error_msg = response.get("remarks", "Unknown error") if response else "No response from broker"
                logger.error(f"Forever Order placement failed: {error_msg}")
                return {
                    "status": "failed",
                    "message": error_msg,
                    "raw_response": response
                }
        except Exception as e:
            logger.error(f"Exception placing Forever Order: {e}")
            return {
                "status": "error",
                "message": str(e),
                "raw_response": None
            }
