#!/usr/bin/env python3
"""Test OAuth flow with improved tokenId extraction"""

from dhan_auth import load_auth_from_env
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

print('🔄 Testing improved OAuth flow with URL tokenId extraction...')
print('👀 Watch the browser window - it will capture tokenId from URL!')
print()

auth = load_auth_from_env()

if auth:
    new_token = auth.generate_new_token()
    
    if new_token:
        print()
        print('='*60)
        print('🎉 SUCCESS! Token generated and saved!')
        print('='*60)
        print(f'Token (first 50 chars): {new_token[:50]}...')
        print(f'Expires: {auth._token_expiry}')
        print()
        print('✅ Local .env file has been updated')
        print()
        print('📋 To deploy to Cloud Run:')
        print('cd /Users/abhishekshah/Desktop/quantlab-workspace/webhook-service && ./deploy.sh')
        print()
    else:
        print()
        print('❌ Token generation failed')
else:
    print('❌ Failed to load auth')
