#!/usr/bin/env python3
"""
Unit tests for core/config_manager.py
Tests centralized configuration management
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config_manager import ConfigManager, get_config


class TestConfigManager:
    """Test ConfigManager class"""
    
    def test_singleton_pattern(self):
        """Test that get_config returns same instance"""
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2, "ConfigManager should be a singleton"
    
    def test_get_basic_value(self):
        """Test getting a basic configuration value"""
        config = get_config()
        
        # Test with environment variable
        with patch.dict(os.environ, {'TEST_KEY': 'test_value'}):
            assert config.get('TEST_KEY') == 'test_value'
    
    def test_get_with_default(self):
        """Test getting value with default fallback"""
        config = get_config()
        
        # Non-existent key should return default
        assert config.get('NONEXISTENT_KEY', 'default') == 'default'
    
    def test_get_dhan_config(self):
        """Test getting Dhan configuration"""
        config = get_config()
        
        test_env = {
            'DHAN_CLIENT_ID': '1234567890',
            'DHAN_ACCESS_TOKEN': 'test_token',
            'DHAN_API_KEY': 'test_api_key',
            'DHAN_API_SECRET': 'test_api_secret'
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            # Force reload
            config._config = None
            config._load_config()
            
            dhan_config = config.get_dhan_config()
            assert dhan_config['client_id'] == '1234567890'
            assert dhan_config['access_token'] == 'test_token'
            assert dhan_config['api_key'] == 'test_api_key'
            assert dhan_config['api_secret'] == 'test_api_secret'
    
    def test_update_token(self):
        """Test updating access token"""
        config = get_config()
        
        # This should not raise an error
        config.update_token('new_token_value', 7200)
        
        # Verify token is stored in config
        assert config.get('DHAN_ACCESS_TOKEN') == 'new_token_value'
    
    def test_validate_required_keys(self):
        """Test validation of required keys"""
        config = get_config()
        
        # Test with all required keys present
        test_env = {
            'KEY1': 'value1',
            'KEY2': 'value2',
            'KEY3': 'value3'
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            config._config = None
            config._load_config()
            
            # Should not raise
            missing = config.validate(['KEY1', 'KEY2', 'KEY3'])
            assert len(missing) == 0
            
            # Test with missing keys
            missing = config.validate(['KEY1', 'KEY2', 'MISSING_KEY'])
            assert 'MISSING_KEY' in missing
    
    def test_environment_precedence(self):
        """Test that environment variables take precedence"""
        config = get_config()
        
        # Environment variable should override .env file
        with patch.dict(os.environ, {'TEST_PRIORITY': 'env_value'}):
            config._config = None
            config._load_config()
            assert config.get('TEST_PRIORITY') == 'env_value'
    
    def test_secret_manager_integration(self):
        """Test Secret Manager integration (mocked)"""
        config = get_config()
        
        # Mock Secret Manager client
        with patch('core.config_manager.secretmanager') as mock_sm:
            mock_client = MagicMock()
            mock_sm.SecretManagerServiceClient.return_value = mock_client
            
            # Mock secret access
            mock_response = MagicMock()
            mock_response.payload.data.decode.return_value = 'secret_value'
            mock_client.access_secret_version.return_value = mock_response
            
            # This tests that the method doesn't crash
            # Actual Secret Manager calls are only in production
            config._config = None
            config._load_config()
    
    def test_config_keys_property(self):
        """Test getting all configuration keys"""
        config = get_config()
        
        with patch.dict(os.environ, {'TEST_KEY1': 'value1', 'TEST_KEY2': 'value2'}):
            config._config = None
            config._load_config()
            
            keys = config.keys()
            assert 'TEST_KEY1' in keys
            assert 'TEST_KEY2' in keys
    
    def test_config_items_property(self):
        """Test getting all configuration items"""
        config = get_config()
        
        with patch.dict(os.environ, {'TEST_ITEM': 'test_value'}):
            config._config = None
            config._load_config()
            
            items = dict(config.items())
            assert items.get('TEST_ITEM') == 'test_value'


class TestConfigManagerEdgeCases:
    """Test edge cases and error handling"""
    
    def test_empty_key(self):
        """Test handling of empty key"""
        config = get_config()
        assert config.get('') is None
        assert config.get('', 'default') == 'default'
    
    def test_none_key(self):
        """Test handling of None key"""
        config = get_config()
        with pytest.raises((TypeError, AttributeError)):
            config.get(None)
    
    def test_special_characters_in_value(self):
        """Test configuration values with special characters"""
        config = get_config()
        
        special_value = 'test!@#$%^&*()_+-={}[]|\\:";\'<>?,./'
        with patch.dict(os.environ, {'SPECIAL_KEY': special_value}):
            config._config = None
            config._load_config()
            assert config.get('SPECIAL_KEY') == special_value
    
    def test_multiline_value(self):
        """Test configuration values with newlines"""
        config = get_config()
        
        multiline_value = 'line1\nline2\nline3'
        with patch.dict(os.environ, {'MULTILINE_KEY': multiline_value}):
            config._config = None
            config._load_config()
            assert config.get('MULTILINE_KEY') == multiline_value


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
