"""
Dhan Forever Orders (GTT - Good Till Triggered) Module
Supports placing and managing Forever Orders through Dhan API
"""

from __future__ import annotations

import logging
import requests

from dhanhq import dhanhq

logger = logging.getLogger(__name__)


class DhanForeverOrders:
    """Dhan Forever Orders (GTT) management"""
    
    API_BASE_URL = "https://api.dhan.co/v2"
    
    def __init__(self, client_id: str, access_token: str):
        """
        Initialize Forever Orders client
        
        Args:
            client_id: Dhan client ID
            access_token: Valid Dhan access token
        """
        self.client_id = client_id
        self.access_token = access_token
        self.dhan = dhanhq(client_id, access_token)
        self.headers = {
            "access-token": access_token,
            "Content-Type": "application/json"
        }
        logger.info("✅ Forever Orders module initialized")
    
    def place_forever_order(
        self,
        security_id: str,
        exchange: str,
        transaction_type: str,
        product_type: str,
        order_type: str,
        quantity: int,
        price: float,
        trigger_price: float,
        validity: str = "DAY",
        order_flag: str = "SINGLE",
        correlation_id: str | None = None
    ) -> dict:
        """
        Place a Forever Order (GTT)
        
        Args:
            security_id: Dhan security ID
            exchange: Exchange segment (NSE_EQ, BSE_EQ, etc.)
            transaction_type: BUY or SELL
            product_type: CNC or MTF
            order_type: LIMIT or MARKET
            quantity: Number of shares
            price: Target price
            trigger_price: Trigger price (order placed when this is hit)
            validity: DAY or IOC
            order_flag: SINGLE (basic GTT) or OCO (One Cancels Other)
            correlation_id: Optional tracking ID
            
        Returns:
            dict with status, order_id, message
        """
        try:
            logger.info(
                f"📌 Placing Forever Order: {transaction_type} {quantity} @ "
                f"trigger={trigger_price}, price={price}"
            )
            
            # Build order data
            order_data = {
                "dhanClientId": self.client_id,
                "orderFlag": order_flag,
                "transactionType": transaction_type,
                "exchangeSegment": exchange,
                "productType": product_type,
                "orderType": order_type,
                "validity": validity,
                "securityId": str(security_id),
                "quantity": quantity,
                "price": price,
                "triggerPrice": trigger_price
            }
            
            if correlation_id:
                order_data["correlationId"] = correlation_id
            
            # Place forever order using direct API call
            url = f"{self.API_BASE_URL}/forever/orders"
            logger.info(f"Sending POST to {url}")
            logger.info(f"Payload: {order_data}")
            
            response = requests.post(
                url,
                json=order_data,
                headers=self.headers,
                timeout=10
            )
            
            logger.info(f"Status Code: {response.status_code}")
            logger.info(f"Response: {response.text}")
            
            # Check HTTP status
            if response.status_code != 200:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("errorMessage") or error_data.get("message") or response.text
                    logger.error(f"❌ HTTP {response.status_code}: {error_msg}")
                    return {
                        "status": "failed",
                        "order_id": None,
                        "message": f"HTTP {response.status_code}: {error_msg}"
                    }
                except:
                    logger.error(f"❌ HTTP {response.status_code}: {response.text}")
                    return {
                        "status": "failed",
                        "order_id": None,
                        "message": f"HTTP {response.status_code}: {response.text}"
                    }
            
            # Parse successful response
            data = response.json()
            logger.info(f"Forever Order Response: {data}")
            
            # Check response structure
            if isinstance(data, dict):
                order_id = data.get("orderId") or data.get("data", {}).get("orderId")
                order_status = data.get("orderStatus") or data.get("data", {}).get("orderStatus")
                
                if order_id:
                    return {
                        "status": "success",
                        "order_id": order_id,
                        "order_status": order_status,
                        "message": f"Forever Order placed: {order_id}"
                    }
                else:
                    error_msg = data.get("remarks") or data.get("errorMessage") or data.get("message") or "Unknown error"
                    logger.error(f"❌ Forever Order failed: {error_msg}")
                    return {
                        "status": "failed",
                        "order_id": None,
                        "message": f"Forever Order failed: {error_msg}"
                    }
            else:
                logger.error(f"❌ Unexpected response format: {data}")
                return {
                    "status": "failed",
                    "order_id": None,
                    "message": f"Unexpected response: {data}"
                }
                
        except Exception as e:
            logger.error(f"❌ Exception placing forever order: {e}")
            return {
                "status": "failed",
                "order_id": None,
                "message": f"Exception: {str(e)}"
            }
    
    def get_all_forever_orders(self) -> list:
        """
        Get all existing Forever Orders using direct API call
        
        Returns:
            List of forever orders
        """
        try:
            logger.info("📋 Fetching all Forever Orders")
            url = f"{self.API_BASE_URL}/forever/orders"
            
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if isinstance(data, dict) and "data" in data:
                orders = data["data"]
                logger.info(f"✅ Found {len(orders)} Forever Orders")
                return orders
            elif isinstance(data, list):
                logger.info(f"✅ Found {len(data)} Forever Orders")
                return data
            else:
                logger.warning(f"⚠️  Unexpected response format: {data}")
                return []
                
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP error fetching forever orders: {e}")
            logger.error(f"Response: {e.response.text if e.response else 'No response'}")
            return []
        except Exception as e:
            logger.error(f"❌ Exception fetching forever orders: {e}")
            return []
    
    def cancel_forever_order(self, order_id: str) -> dict:
        """
        Cancel a Forever Order
        
        Args:
            order_id: Forever order ID to cancel
            
        Returns:
            dict with status and message
        """
        try:
            logger.info(f"🗑️  Cancelling Forever Order: {order_id}")
            response = self.dhan.cancel_forever_order(order_id)
            
            if isinstance(response, dict):
                status = response.get("orderStatus")
                if status == "CANCELLED":
                    logger.info(f"✅ Forever Order cancelled: {order_id}")
                    return {
                        "status": "success",
                        "message": f"Forever Order {order_id} cancelled"
                    }
            
            logger.warning(f"⚠️  Unexpected cancellation response: {response}")
            return {
                "status": "failed",
                "message": f"Cancellation uncertain: {response}"
            }
            
        except Exception as e:
            logger.error(f"❌ Exception cancelling forever order: {e}")
            return {
                "status": "failed",
                "message": f"Exception: {str(e)}"
            }
    
    def modify_forever_order(
        self,
        order_id: str,
        quantity: int | None = None,
        price: float | None = None,
        trigger_price: float | None = None,
        order_type: str | None = None,
        validity: str | None = None
    ) -> dict:
        """
        Modify an existing Forever Order
        
        Args:
            order_id: Forever order ID
            quantity: New quantity (optional)
            price: New price (optional)
            trigger_price: New trigger price (optional)
            order_type: New order type (optional)
            validity: New validity (optional)
            
        Returns:
            dict with status and message
        """
        try:
            logger.info(f"✏️  Modifying Forever Order: {order_id}")
            
            # Build modification data
            modify_data = {
                "dhanClientId": self.client_id,
                "orderId": order_id,
                "orderFlag": "SINGLE",
                "legName": "TARGET_LEG"
            }
            
            if quantity is not None:
                modify_data["quantity"] = quantity
            if price is not None:
                modify_data["price"] = price
            if trigger_price is not None:
                modify_data["triggerPrice"] = trigger_price
            if order_type is not None:
                modify_data["orderType"] = order_type
            if validity is not None:
                modify_data["validity"] = validity
            
            response = self.dhan.modify_forever_order(order_id, modify_data)
            
            logger.info(f"Modification response: {response}")
            
            if isinstance(response, dict):
                status = response.get("orderStatus")
                if status == "PENDING":
                    return {
                        "status": "success",
                        "message": f"Forever Order {order_id} modified"
                    }
            
            return {
                "status": "failed",
                "message": f"Modification uncertain: {response}"
            }
            
        except Exception as e:
            logger.error(f"❌ Exception modifying forever order: {e}")
            return {
                "status": "failed",
                "message": f"Exception: {str(e)}"
            }
    
    def set_static_ip(self, ip_address: str) -> dict:
        """
        Set static IP for API access (required for order placement)
        
        Args:
            ip_address: IP address to whitelist
            
        Returns:
            dict with status and message
        """
        try:
            logger.info(f"🔒 Setting static IP: {ip_address}")
            url = f"{self.API_BASE_URL}/auth/static-ip"
            
            payload = {"ipAddress": ip_address}
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"✅ Static IP set successfully: {data}")
            
            return {
                "status": "success",
                "message": f"Static IP {ip_address} whitelisted",
                "data": data
            }
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP error setting static IP: {e}")
            logger.error(f"Response: {e.response.text if e.response else 'No response'}")
            return {
                "status": "failed",
                "message": f"HTTP Error: {e}"
            }
        except Exception as e:
            logger.error(f"❌ Exception setting static IP: {e}")
            return {
                "status": "failed",
                "message": f"Exception: {str(e)}"
            }
    
    def get_static_ip(self) -> dict:
        """
        Get current whitelisted static IP
        
        Returns:
            dict with status and IP address
        """
        try:
            logger.info("🔍 Fetching static IP configuration")
            url = f"{self.API_BASE_URL}/auth/static-ip"
            
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"✅ Static IP configuration: {data}")
            
            return {
                "status": "success",
                "data": data
            }
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP error fetching static IP: {e}")
            logger.error(f"Response: {e.response.text if e.response else 'No response'}")
            return {
                "status": "failed",
                "message": f"HTTP Error: {e}"
            }
        except Exception as e:
            logger.error(f"❌ Exception fetching static IP: {e}")
            return {
                "status": "failed",
                "message": f"Exception: {str(e)}"
            }
    
    def modify_static_ip(self, ip_address: str) -> dict:
        """
        Modify whitelisted static IP
        
        Args:
            ip_address: New IP address to whitelist
            
        Returns:
            dict with status and message
        """
        try:
            logger.info(f"🔄 Modifying static IP to: {ip_address}")
            url = f"{self.API_BASE_URL}/auth/static-ip"
            
            payload = {"ipAddress": ip_address}
            response = requests.put(url, headers=self.headers, json=payload, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"✅ Static IP modified successfully: {data}")
            
            return {
                "status": "success",
                "message": f"Static IP updated to {ip_address}",
                "data": data
            }
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP error modifying static IP: {e}")
            logger.error(f"Response: {e.response.text if e.response else 'No response'}")
            return {
                "status": "failed",
                "message": f"HTTP Error: {e}"
            }
        except Exception as e:
            logger.error(f"❌ Exception modifying static IP: {e}")
            return {
                "status": "failed",
                "message": f"Exception: {str(e)}"
            }


# Helper function for webhook integration
def create_forever_order_from_webhook(
    dhan_client,
    leg,
    security_id: str,
    trigger_price: float
) -> dict:
    """
    Create Forever Order from webhook order leg
    
    Args:
        dhan_client: DhanClient instance
        leg: OrderLeg from webhook payload
        security_id: Dhan security ID
        trigger_price: Trigger price for Forever Order
        
    Returns:
        dict with status and order details
    """
    try:
        # Initialize Forever Orders module
        forever = DhanForeverOrders(
            client_id=dhan_client.client_id,
            access_token=dhan_client.access_token
        )
        
        # Map product types (Forever Orders only support CNC and MTF)
        product_type_map = {
            "C": "CNC",
            "CNC": "CNC",
            "M": "MTF",
            "MTF": "MTF",
            "I": "CNC",  # Convert Intraday to CNC for Forever Orders
            "INTRADAY": "CNC"
        }
        
        product_type = product_type_map.get(leg.productType, "CNC")
        
        # Place Forever Order
        result = forever.place_forever_order(
            security_id=security_id,
            exchange=leg.exchange,
            transaction_type=leg.transactionType,
            product_type=product_type,
            order_type=leg.orderType,
            quantity=int(leg.quantity),
            price=float(leg.price) if leg.price else 0.0,
            trigger_price=trigger_price,
            validity="DAY"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Exception creating forever order from webhook: {e}")
        return {
            "status": "failed",
            "order_id": None,
            "message": f"Exception: {str(e)}"
        }
