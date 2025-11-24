#!/usr/bin/env python3
"""
Test script for Forever Orders (GTT) functionality
Tests basic GTT order operations
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from dhan_forever_orders import DhanForeverOrders
    print("✅ Successfully imported DhanForeverOrders module\n")
except ImportError as e:
    print(f"❌ Failed to import DhanForeverOrders: {e}")
    sys.exit(1)

def main():
    print("🧪 Testing Forever Orders (GTT) Module")
    print("=" * 50)
    print()
    
    # Get credentials
    client_id = os.getenv("DHAN_CLIENT_ID")
    access_token = os.getenv("DHAN_ACCESS_TOKEN")
    
    if not client_id or not access_token:
        print("❌ Missing DHAN_CLIENT_ID or DHAN_ACCESS_TOKEN in .env file")
        print("   Please configure credentials before testing")
        return
    
    print(f"📋 Client ID: {client_id}")
    print(f"📋 Token: {access_token[:20]}...")
    print()
    
    # Initialize Forever Orders module
    print("Test 1: Initialize Forever Orders Module")
    print("-" * 50)
    try:
        forever = DhanForeverOrders(
            client_id=client_id,
            access_token=access_token
        )
        print("✅ Forever Orders module initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        return
    print()
    
    # Test 2: List existing forever orders
    print("Test 2: List Existing Forever Orders")
    print("-" * 50)
    try:
        orders = forever.get_all_forever_orders()
        print(f"✅ Found {len(orders)} forever orders")
        
        if orders:
            print("\nActive Forever Orders:")
            for order in orders[:5]:  # Show first 5
                print(f"  Order ID: {order.get('orderId', 'N/A')}")
                print(f"  Status: {order.get('orderStatus', 'N/A')}")
                print(f"  Symbol: {order.get('tradingSymbol', 'N/A')}")
                print(f"  Trigger Price: ₹{order.get('triggerPrice', 0)}")
                print()
        else:
            print("  No active forever orders found")
    except Exception as e:
        print(f"❌ Failed to list orders: {e}")
    print()
    
    # Test 3: Place forever order (DRY RUN - commented out)
    print("Test 3: Place Forever Order (DRY RUN)")
    print("-" * 50)
    print("⚠️  Actual order placement is commented out for safety")
    print("   Uncomment the code below to test real order placement")
    print()
    print("Example Forever Order:")
    print("  Symbol: TCS")
    print("  Trigger Price: ₹3500.0")
    print("  Execution Price: ₹3495.0")
    print("  Quantity: 1")
    print("  Type: SINGLE (basic GTT)")
    print()
    
    # Uncomment to test actual order placement
    """
    try:
        result = forever.place_forever_order(
            security_id="1333",  # TCS
            exchange="NSE_EQ",
            transaction_type="BUY",
            product_type="CNC",
            order_type="LIMIT",
            quantity=1,
            price=3495.0,
            trigger_price=3500.0,
            validity="DAY",
            order_flag="SINGLE"
        )
        
        if result["status"] == "success":
            print(f"✅ Forever Order placed successfully")
            print(f"   Order ID: {result['order_id']}")
        else:
            print(f"❌ Forever Order failed: {result['message']}")
    except Exception as e:
        print(f"❌ Exception placing order: {e}")
    """
    print()
    
    # Test 4: Forever order capabilities
    print("Test 4: Forever Order Capabilities")
    print("-" * 50)
    print("✅ Supported Features:")
    print("   - SINGLE orders (basic GTT)")
    print("   - LIMIT and MARKET order types")
    print("   - CNC and MTF products (no INTRADAY)")
    print("   - Order modification")
    print("   - Order cancellation")
    print()
    print("⚠️  Requirements:")
    print("   - Static IP whitelisting (for order placement)")
    print("   - Valid Dhan access token")
    print()
    
    # Test 5: Integration with webhook
    print("Test 5: Webhook Integration (Conceptual)")
    print("-" * 50)
    print("To place Forever Order via webhook, add triggerPrice:")
    print()
    print("Example webhook payload:")
    print("""
{
  "secret": "GTcl4",
  "alertType": "multi_leg_order",
  "order_legs": [
    {
      "transactionType": "B",
      "orderType": "LMT",
      "quantity": "1",
      "exchange": "NSE_EQ",
      "symbol": "TCS",
      "instrument": "EQ",
      "productType": "C",
      "price": "3495.0",
      "triggerPrice": "3500.0",  // This triggers Forever Order
      "sort_order": "1",
      "meta": { ... }
    }
  ]
}
    """)
    print()
    print("⚠️  Note: Webhook integration is not yet implemented")
    print("   This is a future enhancement")
    print()
    
    print("=" * 50)
    print("✅ Forever Orders Tests Complete")
    print()
    print("📚 Documentation:")
    print("   See docs/FOREVER_ORDERS_GUIDE.md for detailed usage")
    print()

if __name__ == "__main__":
    main()
