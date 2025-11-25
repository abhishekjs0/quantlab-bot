"""
Standalone OAuth Service Interface
Can be used by both webhook service and backtesting tools.
Provides a clean API for token management without tight coupling.
"""

import asyncio
import logging
import sys
from typing import Optional
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path to import from core
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config_manager import get_config

logger = logging.getLogger(__name__)


class OAuthServiceInterface:
    """
    High-level interface for Dhan OAuth operations.
    Abstracts away implementation details for easy use.
    """
    
    def __init__(self):
        self.config = get_config()
        self._dhan_auth = None
        self._initialized = False
    
    def _init_dhan_auth(self):
        """Lazy initialization of DhanAuth"""
        if self._initialized:
            return
        
        try:
            # Import here to avoid circular dependency
            import sys
            import os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'webhook-service'))
            from dhan_auth import DhanAuth
            
            dhan_config = self.config.get_dhan_config()
            
            self._dhan_auth = DhanAuth(
                client_id=dhan_config["client_id"],
                api_key=dhan_config["api_key"],
                api_secret=dhan_config["api_secret"],
                user_id=dhan_config["user_id"],
                password=dhan_config["password"],
                totp_secret=dhan_config["totp_secret"],
                pin=dhan_config["pin"],
                access_token=dhan_config["access_token"],
                redirect_uri=dhan_config["redirect_uri"],
                gcp_project=self.config.gcp_project
            )
            
            self._initialized = True
            logger.info("✅ OAuth service initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize OAuth service: {e}")
            raise
    
    async def get_valid_token(self, auto_refresh: bool = True) -> Optional[str]:
        """
        Get a valid access token, auto-refreshing if needed.
        
        Args:
            auto_refresh: Whether to automatically refresh expired tokens
            
        Returns:
            Valid access token or None
        """
        self._init_dhan_auth()
        
        try:
            token = await self._dhan_auth.get_valid_token(auto_refresh=auto_refresh)
            return token
        except Exception as e:
            logger.error(f"Failed to get valid token: {e}")
            return None
    
    async def force_refresh_token(self) -> Optional[str]:
        """
        Force generate a new token regardless of current validity.
        
        Returns:
            New access token or None
        """
        self._init_dhan_auth()
        
        try:
            token = await self._dhan_auth.force_refresh_token()
            return token
        except Exception as e:
            logger.error(f"Failed to force refresh token: {e}")
            return None
    
    def get_token_expiry(self) -> Optional[datetime]:
        """
        Get current token expiry time.
        
        Returns:
            Expiry datetime or None
        """
        self._init_dhan_auth()
        return self._dhan_auth._token_expiry if self._dhan_auth else None
    
    def get_token_status(self) -> dict:
        """
        Get comprehensive token status information.
        
        Returns:
            Dictionary with token status details
        """
        self._init_dhan_auth()
        
        expiry = self.get_token_expiry()
        
        if not expiry:
            return {
                "valid": False,
                "expiry": None,
                "hours_remaining": 0,
                "needs_refresh": True
            }
        
        now = datetime.now()
        time_remaining = (expiry - now).total_seconds() / 3600
        
        return {
            "valid": time_remaining > 0,
            "expiry": expiry.isoformat(),
            "hours_remaining": max(0, time_remaining),
            "needs_refresh": time_remaining < 1.0
        }


# Singleton instance
_oauth_service: Optional[OAuthServiceInterface] = None


def get_oauth_service() -> OAuthServiceInterface:
    """Get or create global OAuth service instance"""
    global _oauth_service
    if _oauth_service is None:
        _oauth_service = OAuthServiceInterface()
    return _oauth_service


# ============================================================================
# CONVENIENCE FUNCTIONS FOR EASY USE
# ============================================================================

async def get_dhan_token(auto_refresh: bool = True) -> Optional[str]:
    """
    Quick access to get a valid Dhan token.
    
    Usage in backtesting:
        from oauth_service import get_dhan_token
        
        token = await get_dhan_token()
        dhan_client = DhanClient(token)
    
    Args:
        auto_refresh: Whether to auto-refresh if expired
        
    Returns:
        Valid access token or None
    """
    service = get_oauth_service()
    return await service.get_valid_token(auto_refresh=auto_refresh)


def get_dhan_token_sync() -> Optional[str]:
    """
    Synchronous version for use in non-async code.
    
    Usage in backtesting:
        from oauth_service import get_dhan_token_sync
        
        token = get_dhan_token_sync()
        dhan_client = DhanClient(token)
    
    Returns:
        Valid access token or None
    """
    service = get_oauth_service()
    return asyncio.run(service.get_valid_token())


def check_token_status() -> dict:
    """
    Quick check of current token status.
    
    Usage:
        from oauth_service import check_token_status
        
        status = check_token_status()
        print(f"Token valid: {status['valid']}, expires in {status['hours_remaining']:.1f}h")
    
    Returns:
        Dictionary with token status
    """
    service = get_oauth_service()
    return service.get_token_status()


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    import sys
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Example 1: Check token status
    print("\n=== Token Status ===")
    status = check_token_status()
    print(f"Valid: {status['valid']}")
    print(f"Expiry: {status['expiry']}")
    print(f"Hours remaining: {status['hours_remaining']:.1f}")
    print(f"Needs refresh: {status['needs_refresh']}")
    
    # Example 2: Get token (async)
    print("\n=== Getting Token (Async) ===")
    async def test_async():
        token = await get_dhan_token()
        if token:
            print(f"✅ Got token: {token[:50]}...")
        else:
            print("❌ Failed to get token")
    
    asyncio.run(test_async())
    
    # Example 3: Get token (sync)
    print("\n=== Getting Token (Sync) ===")
    token = get_dhan_token_sync()
    if token:
        print(f"✅ Got token: {token[:50]}...")
    else:
        print("❌ Failed to get token")
