#!/usr/bin/env python3
"""
Test Forever Orders (GTT) - Live Testing
Creates a Forever Order to sell 3 shares of SWIGGY at MKT
"""

import os
from dotenv import load_dotenv
from dhan_forever_orders import DhanForeverOrders

# Load environment
load_dotenv()

def main():
    """Test Forever Orders creation and retrieval"""
    
    # Get credentials
    client_id = os.getenv("DHAN_CLIENT_ID")
    access_token = os.getenv("DHAN_ACCESS_TOKEN")
    
    if not client_id or not access_token:
        print("❌ Error: DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN required")
        return
    
    print("🧪 Forever Orders (GTT) Live Test")
    print("=" * 50)
    
    # Initialize Forever Orders client
    forever = DhanForeverOrders(client_id, access_token)
    
    # Test 1: Get all existing Forever Orders
    print("\n📋 Test 1: Fetching existing Forever Orders...")
    try:
        orders = forever.get_all_forever_orders()
        print(f"✅ Found {len(orders)} existing Forever Orders")
        if orders:
            for idx, order in enumerate(orders, 1):
                print(f"   {idx}. {order.get('tradingSymbol', 'N/A')} - "
                      f"{order.get('transactionType', 'N/A')} - "
                      f"Status: {order.get('orderStatus', 'N/A')}")
        else:
            print("   (No existing Forever Orders)")
    except Exception as e:
        print(f"❌ Error fetching orders: {e}")
        return
    
    # Test 2: Create Forever Order - SWIGGY SELL 3 @ MKT
    print("\n🆕 Test 2: Creating Forever Order...")
    print("   Symbol: SWIGGY")
    print("   Action: SELL")
    print("   Quantity: 3")
    print("   Type: MARKET")
    print("   Trigger: ₹450 (example)")
    
    try:
        # SWIGGY details
        security_id = "27066"
        exchange = "NSE"
        symbol = "SWIGGY"
        
        # Order parameters
        transaction_type = "SELL"
        quantity = 3
        order_type = "MARKET"
        product_type = "CNC"  # Cash and Carry
        trigger_price = 450.0  # Example trigger price
        price = 0.0  # For MARKET orders
        
        print(f"\n📤 Creating Forever Order...")
        print(f"   Security ID: {security_id}")
        print(f"   Exchange: NSE_EQ")
        print(f"   Trigger Price: ₹{trigger_price}")
        
        # Create the Forever Order
        result = forever.place_forever_order(
            security_id=security_id,
            exchange="NSE_EQ",
            transaction_type=transaction_type,
            product_type=product_type,
            order_type=order_type,
            quantity=quantity,
            price=price,
            trigger_price=trigger_price,
            validity="DAY"
        )
        
        print(f"✅ Forever Order created successfully!")
        print(f"   Response: {result}")
        
    except Exception as e:
        print(f"❌ Error creating Forever Order: {e}")
        print(f"   Details: {str(e)}")
        return
    
    # Test 3: Fetch orders again to verify
    print("\n🔍 Test 3: Verifying order creation...")
    try:
        orders = forever.get_all_forever_orders()
        print(f"✅ Total Forever Orders now: {len(orders)}")
        
        # Look for our SWIGGY order
        swiggy_orders = [o for o in orders if "SWIGGY" in str(o.get("tradingSymbol", ""))]
        if swiggy_orders:
            print(f"\n📊 SWIGGY Forever Orders:")
            for order in swiggy_orders:
                print(f"   Order ID: {order.get('orderId', 'N/A')}")
                print(f"   Symbol: {order.get('tradingSymbol', 'N/A')}")
                print(f"   Type: {order.get('transactionType', 'N/A')}")
                print(f"   Quantity: {order.get('quantity', 'N/A')}")
                print(f"   Trigger: ₹{order.get('triggerPrice', 'N/A')}")
                print(f"   Status: {order.get('orderStatus', 'N/A')}")
                print()
        else:
            print("   ⚠️ SWIGGY order not found in list")
            
    except Exception as e:
        print(f"❌ Error verifying orders: {e}")
    
    print("=" * 50)
    print("✅ Forever Orders test complete")

if __name__ == "__main__":
    main()
