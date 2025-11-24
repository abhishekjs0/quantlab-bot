#!/usr/bin/env python3
"""
Test SELL order validation logic
Tests portfolio/position checking before allowing SELL orders
"""

import json
import requests
from datetime import datetime

# Configuration
WEBHOOK_URL = "http://localhost:8080/webhook"
WEBHOOK_SECRET = "GTcl4"

def send_webhook(payload):
    """Send webhook payload to local server"""
    headers = {"Content-Type": "application/json"}
    response = requests.post(WEBHOOK_URL, json=payload, headers=headers)
    return response.json()

def test_buy_order():
    """Test BUY order - should pass without validation"""
    print("\n" + "="*60)
    print("TEST 1: BUY Order (should pass without portfolio check)")
    print("="*60)
    
    payload = {
        "secret": WEBHOOK_SECRET,
        "alertType": "multi_leg_order",
        "order_legs": [
            {
                "transactionType": "B",
                "orderType": "MKT",
                "quantity": "10",
                "exchange": "NSE",
                "symbol": "RELIANCE",
                "instrument": "EQ",
                "productType": "C",
                "sort_order": "1",
                "price": "0",
                "meta": {
                    "interval": "1D",
                    "time": datetime.now().isoformat(),
                    "timenow": datetime.now().isoformat()
                }
            }
        ]
    }
    
    result = send_webhook(payload)
    print(f"\nResponse: {json.dumps(result, indent=2)}")
    return result

def test_sell_order_with_holdings():
    """Test SELL order - should validate holdings"""
    print("\n" + "="*60)
    print("TEST 2: SELL Order with CNC product type (checks holdings)")
    print("="*60)
    
    payload = {
        "secret": WEBHOOK_SECRET,
        "alertType": "multi_leg_order",
        "order_legs": [
            {
                "transactionType": "S",
                "orderType": "MKT",
                "quantity": "5",
                "exchange": "NSE",
                "symbol": "RELIANCE",
                "instrument": "EQ",
                "productType": "C",  # CNC = checks holdings
                "sort_order": "1",
                "price": "0",
                "meta": {
                    "interval": "1D",
                    "time": datetime.now().isoformat(),
                    "timenow": datetime.now().isoformat()
                }
            }
        ]
    }
    
    result = send_webhook(payload)
    print(f"\nResponse: {json.dumps(result, indent=2)}")
    return result

def test_sell_order_intraday():
    """Test SELL order with INTRADAY product - should validate positions"""
    print("\n" + "="*60)
    print("TEST 3: SELL Order with INTRADAY product type (checks positions)")
    print("="*60)
    
    payload = {
        "secret": WEBHOOK_SECRET,
        "alertType": "multi_leg_order",
        "order_legs": [
            {
                "transactionType": "S",
                "orderType": "MKT",
                "quantity": "10",
                "exchange": "NSE",
                "symbol": "INFY",
                "instrument": "EQ",
                "productType": "I",  # INTRADAY = checks positions
                "sort_order": "1",
                "price": "0",
                "meta": {
                    "interval": "1D",
                    "time": datetime.now().isoformat(),
                    "timenow": datetime.now().isoformat()
                }
            }
        ]
    }
    
    result = send_webhook(payload)
    print(f"\nResponse: {json.dumps(result, indent=2)}")
    return result

def test_multi_leg_mixed():
    """Test multi-leg order with both BUY and SELL"""
    print("\n" + "="*60)
    print("TEST 4: Multi-leg order (BUY + SELL)")
    print("="*60)
    
    payload = {
        "secret": WEBHOOK_SECRET,
        "alertType": "multi_leg_order",
        "order_legs": [
            {
                "transactionType": "B",
                "orderType": "MKT",
                "quantity": "10",
                "exchange": "NSE",
                "symbol": "TCS",
                "instrument": "EQ",
                "productType": "C",
                "sort_order": "1",
                "price": "0",
                "meta": {
                    "interval": "1D",
                    "time": datetime.now().isoformat(),
                    "timenow": datetime.now().isoformat()
                }
            },
            {
                "transactionType": "S",
                "orderType": "MKT",
                "quantity": "5",
                "exchange": "NSE",
                "symbol": "WIPRO",
                "instrument": "EQ",
                "productType": "C",
                "sort_order": "2",
                "price": "0",
                "meta": {
                    "interval": "1D",
                    "time": datetime.now().isoformat(),
                    "timenow": datetime.now().isoformat()
                }
            }
        ]
    }
    
    result = send_webhook(payload)
    print(f"\nResponse: {json.dumps(result, indent=2)}")
    return result

def main():
    """Run all tests"""
    print("🧪 SELL Order Validation Tests")
    print("=" * 60)
    print("Make sure the webhook service is running:")
    print("  cd webhook-service && python3 app.py")
    print("=" * 60)
    
    try:
        # Test server connectivity
        response = requests.get("http://localhost:8080/health")
        if response.status_code != 200:
            print("❌ Server not responding. Start with: python3 app.py")
            return
        
        print("✅ Server is running\n")
        
        # Run tests
        test_buy_order()
        input("\nPress Enter to continue to next test...")
        
        test_sell_order_with_holdings()
        input("\nPress Enter to continue to next test...")
        
        test_sell_order_intraday()
        input("\nPress Enter to continue to next test...")
        
        test_multi_leg_mixed()
        
        print("\n" + "="*60)
        print("✅ All tests completed!")
        print("="*60)
        print("\nCheck logs for detailed validation output")
        
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to webhook service at http://localhost:8080")
        print("Start the service with: cd webhook-service && python3 app.py")
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n❌ Test error: {e}")

if __name__ == "__main__":
    main()
