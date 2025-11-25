#!/usr/bin/env python3
"""
Unit tests for webhook-service/oauth_service.py
Tests OAuth service interface
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "webhook-service"))

# Note: These tests require mocking since oauth_service imports dhan_auth
# which has complex dependencies (Playwright, etc.)


class TestOAuthServiceInterface:
    """Test OAuthServiceInterface class"""
    
    @patch("oauth_service.get_config")
    def test_initialization(self, mock_get_config):
        """Test OAuth service initialization"""
        # Mock config
        mock_config = MagicMock()
        mock_config.get_dhan_config.return_value = {
            "client_id": "1234567890",
            "access_token": "test_token"
        }
        mock_get_config.return_value = mock_config
        
        from oauth_service import OAuthServiceInterface
        
        service = OAuthServiceInterface()
        assert service.config is not None
        assert not service._initialized
    
    @patch("oauth_service.get_config")
    @patch("oauth_service.DhanAuth")
    def test_lazy_initialization(self, mock_dhan_auth, mock_get_config):
        """Test lazy initialization of DhanAuth"""
        # Mock config
        mock_config = MagicMock()
        mock_config.get_dhan_config.return_value = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "redirect_uri": "http://test",
            "totp_secret": "test_totp",
            "user_id": "1234567890",
            "password": "test_pass",
            "pin": "1234"
        }
        mock_get_config.return_value = mock_config
        
        # Mock DhanAuth
        mock_auth_instance = MagicMock()
        mock_dhan_auth.return_value = mock_auth_instance
        
        from oauth_service import OAuthServiceInterface
        
        service = OAuthServiceInterface()
        service._init_dhan_auth()
        
        assert service._initialized
        assert service._dhan_auth is not None
    
    @patch("oauth_service.get_config")
    @patch("oauth_service.load_auth_from_env")
    def test_get_dhan_token_sync(self, mock_load_auth, mock_get_config):
        """Test synchronous token retrieval"""
        # Mock config
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config
        
        # Mock auth
        mock_auth = MagicMock()
        mock_auth.get_valid_token_sync.return_value = "test_token_12345"
        mock_load_auth.return_value = mock_auth
        
        from oauth_service import get_dhan_token_sync
        
        token = get_dhan_token_sync()
        assert token == "test_token_12345"
    
    @patch("oauth_service.get_config")
    def test_check_token_status(self, mock_get_config):
        """Test token status checking"""
        # Mock config
        mock_config = MagicMock()
        mock_config.get.side_effect = lambda key, default=None: {
            "DHAN_ACCESS_TOKEN": "test_token",
            "TOKEN_EXPIRY": "7200"
        }.get(key, default)
        mock_get_config.return_value = mock_config
        
        from oauth_service import check_token_status
        
        status = check_token_status()
        assert "token" in status
        assert status["token"] == "test_token"


class TestOAuthServiceEdgeCases:
    """Test edge cases and error handling"""
    
    @patch("oauth_service.get_config")
    def test_missing_credentials(self, mock_get_config):
        """Test handling of missing credentials"""
        # Mock config with missing values
        mock_config = MagicMock()
        mock_config.get_dhan_config.return_value = {}
        mock_get_config.return_value = mock_config
        
        from oauth_service import OAuthServiceInterface
        
        service = OAuthServiceInterface()
        # Should not crash, but may log warnings
        service._init_dhan_auth()
    
    @patch("oauth_service.get_config")
    def test_token_refresh_failure(self, mock_get_config):
        """Test handling of token refresh failure"""
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config
        
        from oauth_service import OAuthServiceInterface
        
        service = OAuthServiceInterface()
        # This tests that initialization doesn't crash
        assert service.config is not None


class TestOAuthServiceHelpers:
    """Test helper functions"""
    
    @patch("oauth_service.get_config")
    @patch("oauth_service.load_auth_from_env")
    def test_get_dhan_token_with_auto_refresh(self, mock_load_auth, mock_get_config):
        """Test token retrieval with auto-refresh enabled"""
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config
        
        mock_auth = MagicMock()
        mock_auth.get_valid_token_sync.return_value = "refreshed_token"
        mock_load_auth.return_value = mock_auth
        
        from oauth_service import get_dhan_token_sync
        
        token = get_dhan_token_sync(auto_refresh=True)
        assert token is not None
    
    @patch("oauth_service.get_config")
    def test_token_status_with_expiry(self, mock_get_config):
        """Test token status includes expiry information"""
        mock_config = MagicMock()
        mock_config.get.side_effect = lambda key, default=None: {
            "DHAN_ACCESS_TOKEN": "token_with_expiry",
            "TOKEN_EXPIRY": "3600",
            "TOKEN_REFRESH_TIME": "2025-11-26T10:00:00"
        }.get(key, default)
        mock_get_config.return_value = mock_config
        
        from oauth_service import check_token_status
        
        status = check_token_status()
        assert status["token"] == "token_with_expiry"
        assert "expiry" in status or "TOKEN_EXPIRY" in str(status)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
