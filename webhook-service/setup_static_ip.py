#!/usr/bin/env python3
"""
Static IP Setup Script
Sets up static IP for Dhan order placement
"""

import os
import sys
from dotenv import load_dotenv
from dhan_forever_orders import DhanForeverOrders

# Load environment
load_dotenv()

def main():
    """Setup static IP for Dhan API"""
    
    # Get credentials
    client_id = os.getenv("DHAN_CLIENT_ID")
    access_token = os.getenv("DHAN_ACCESS_TOKEN")
    
    if not client_id or not access_token:
        print("❌ Error: DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN required in .env")
        sys.exit(1)
    
    # Your current public IP
    current_ip = "14.102.163.116"
    
    print("🔧 Static IP Setup for Dhan API")
    print("=" * 50)
    print(f"📍 Your current public IP: {current_ip}")
    print()
    
    # Initialize Forever Orders client
    forever = DhanForeverOrders(client_id, access_token)
    
    try:
        # Check if IP already set
        print("🔍 Checking current static IP...")
        result = forever.get_static_ip()
        
        if result['status'] == 'success' and result['data']:
            print(f"✅ Static IP already configured: {result['data']}")
            
            response = input("\n🤔 Update to current IP? (y/n): ").strip().lower()
            if response == 'y':
                print(f"\n🔄 Updating static IP to {current_ip}...")
                update_result = forever.modify_static_ip(current_ip)
                print(f"✅ {update_result['message']}")
            else:
                print("⏭️  Keeping existing IP")
        else:
            # No IP set, configure new one
            print(f"\n🆕 Setting static IP to {current_ip}...")
            set_result = forever.set_static_ip(current_ip)
            print(f"✅ {set_result['message']}")
        
        # Verify final configuration
        print("\n🔍 Verifying configuration...")
        verify_result = forever.get_static_ip()
        if verify_result['status'] == 'success':
            print(f"✅ Verified static IP: {verify_result['data']}")
            print("\n✅ Static IP setup complete!")
            print("\n📝 Note: If your public IP changes, run this script again")
            print("   or use modify_static_ip() method in your code")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
