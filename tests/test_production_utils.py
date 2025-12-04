#!/usr/bin/env python3
"""
Unit tests for utils/production_utils.py
Tests production utilities: retry, circuit breaker, HMAC, rate limiting
"""

import pytest
import time
import hmac
import hashlib
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.production_utils import (
    retry_with_backoff,
    RetryConfig,
    CircuitBreaker,
    RateLimiter,
    WebhookSecurity,
    verify_hmac_signature,
    generate_hmac_signature,
    MockDhanAPI
)


class TestRetryWithBackoff:
    """Test retry decorator"""
    
    def test_successful_call(self):
        """Test successful call without retries"""
        call_count = [0]
        
        @retry_with_backoff(RetryConfig(max_attempts=3))
        def successful_func():
            call_count[0] += 1
            return "success"
        
        result = successful_func()
        assert result == "success"
        assert call_count[0] == 1
    
    def test_retry_on_failure(self):
        """Test retry after failures"""
        call_count = [0]
        
        @retry_with_backoff(RetryConfig(max_attempts=3, initial_delay=0.01))
        def failing_func():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("Temporary failure")
            return "success"
        
        result = failing_func()
        assert result == "success"
        assert call_count[0] == 3
    
    def test_max_retries_exceeded(self):
        """Test failure after max retries"""
        call_count = [0]
        
        @retry_with_backoff(RetryConfig(max_attempts=2, initial_delay=0.01))
        def always_failing():
            call_count[0] += 1
            raise ValueError("Permanent failure")
        
        with pytest.raises(ValueError):
            always_failing()
        
        assert call_count[0] == 2  # max_attempts = 2
    
    def test_exponential_backoff(self):
        """Test exponential backoff timing"""
        call_times = []
        
        @retry_with_backoff(RetryConfig(max_attempts=3, initial_delay=0.05, exponential_base=2))
        def timed_func():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise ValueError("Retry")
            return "success"
        
        timed_func()
        
        # Check delays increase exponentially
        assert len(call_times) == 3
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]
        # Second delay should be approximately double the first
        assert delay2 >= delay1 * 1.5  # Allow some tolerance
    
    def test_default_config(self):
        """Test retry with default configuration"""
        @retry_with_backoff()
        def simple_func():
            return "default config works"
        
        result = simple_func()
        assert result == "default config works"
    
    def test_specific_exceptions(self):
        """Test retry only catches specified exceptions"""
        call_count = [0]
        
        @retry_with_backoff(RetryConfig(max_attempts=3, exceptions=(ValueError,)))
        def specific_error():
            call_count[0] += 1
            raise TypeError("Different error type")
        
        # TypeError should not be caught, so no retries
        with pytest.raises(TypeError):
            specific_error()
        
        assert call_count[0] == 1  # Only called once, no retry


class TestCircuitBreaker:
    """Test circuit breaker pattern"""
    
    def test_closed_state_initial(self):
        """Test circuit breaker starts in closed state"""
        breaker = CircuitBreaker(failure_threshold=3, timeout=1)
        assert breaker.state == "CLOSED"
    
    def test_open_after_failures(self):
        """Test circuit opens after threshold failures"""
        breaker = CircuitBreaker(failure_threshold=3, timeout=60)
        
        @breaker.call
        def failing_func():
            raise Exception("Failure")
        
        # Record failures through decorated calls
        for _ in range(3):
            try:
                failing_func()
            except Exception:
                pass
        
        assert breaker.state == "OPEN"
    
    def test_success_resets_counter(self):
        """Test successful calls reset failure counter"""
        breaker = CircuitBreaker(failure_threshold=3, timeout=60)
        
        call_count = [0]
        
        @breaker.call
        def intermittent_func():
            call_count[0] += 1
            if call_count[0] <= 2:
                raise Exception("Temporary failure")
            return "success"
        
        # First two calls fail
        for _ in range(2):
            try:
                intermittent_func()
            except Exception:
                pass
        
        # Failure count should be 2
        assert breaker.failure_count == 2
        
        # Third call succeeds, resetting counter
        result = intermittent_func()
        assert result == "success"
        assert breaker.failure_count == 0
        assert breaker.state == "CLOSED"
    
    def test_half_open_state(self):
        """Test circuit transitions to half-open after timeout"""
        breaker = CircuitBreaker(failure_threshold=2, timeout=0.1)
        
        @breaker.call
        def failing_func():
            raise Exception("Failure")
        
        # Open the circuit
        for _ in range(2):
            try:
                failing_func()
            except Exception:
                pass
        
        assert breaker.state == "OPEN"
        
        # Wait for timeout
        time.sleep(0.15)
        
        # Next call should transition to HALF_OPEN
        # The call will still fail but state changes
        try:
            failing_func()
        except Exception:
            pass
        
        # After failure in HALF_OPEN, should go back to OPEN
        assert breaker.state == "OPEN"
    
    def test_circuit_open_blocks_calls(self):
        """Test that open circuit blocks calls immediately"""
        breaker = CircuitBreaker(failure_threshold=2, timeout=60)
        
        @breaker.call
        def failing_func():
            raise Exception("Failure")
        
        # Open the circuit
        for _ in range(2):
            try:
                failing_func()
            except Exception:
                pass
        
        # Now try a call - should raise immediately
        with pytest.raises(Exception, match="Circuit breaker OPEN"):
            failing_func()


class TestWebhookSecurity:
    """Test webhook security utilities"""
    
    def test_generate_signature(self):
        """Test HMAC signature generation"""
        payload = '{"alert": "BUY", "symbol": "RELIANCE"}'
        secret = "test-secret-key"
        
        signature = WebhookSecurity.generate_signature(payload, secret)
        
        # Verify it's a valid hex string
        assert isinstance(signature, str)
        assert len(signature) == 64  # SHA256 produces 64 hex chars
        
        # Verify it's the expected HMAC
        expected = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        assert signature == expected
    
    def test_verify_signature_valid(self):
        """Test valid signature verification"""
        payload = '{"alert": "BUY", "symbol": "RELIANCE"}'
        secret = "test-secret-key"
        
        signature = WebhookSecurity.generate_signature(payload, secret)
        is_valid = WebhookSecurity.verify_signature(payload, signature, secret)
        
        assert is_valid is True
    
    def test_verify_signature_invalid(self):
        """Test invalid signature rejection"""
        payload = '{"alert": "BUY", "symbol": "RELIANCE"}'
        secret = "test-secret-key"
        
        # Use a completely wrong signature
        wrong_signature = "a" * 64
        is_valid = WebhookSecurity.verify_signature(payload, wrong_signature, secret)
        
        assert is_valid is False
    
    def test_verify_signature_wrong_secret(self):
        """Test signature fails with wrong secret"""
        payload = '{"alert": "BUY", "symbol": "RELIANCE"}'
        
        signature = WebhookSecurity.generate_signature(payload, "secret1")
        is_valid = WebhookSecurity.verify_signature(payload, signature, "secret2")
        
        assert is_valid is False
    
    def test_generate_api_key(self):
        """Test API key generation"""
        key = WebhookSecurity.generate_api_key()
        
        assert isinstance(key, str)
        assert len(key) == 64  # 32 bytes = 64 hex chars
        
        # Each key should be unique
        key2 = WebhookSecurity.generate_api_key()
        assert key != key2
    
    def test_generate_api_key_custom_length(self):
        """Test API key generation with custom length"""
        key = WebhookSecurity.generate_api_key(length=16)
        
        assert len(key) == 32  # 16 bytes = 32 hex chars


class TestConvenienceFunctions:
    """Test convenience wrapper functions"""
    
    def test_verify_hmac_signature(self):
        """Test convenience verify function"""
        payload = '{"test": "data"}'
        secret = "my-secret"
        
        signature = generate_hmac_signature(payload, secret)
        is_valid = verify_hmac_signature(payload, signature, secret)
        
        assert is_valid is True
    
    def test_generate_hmac_signature(self):
        """Test convenience generate function"""
        payload = '{"test": "data"}'
        secret = "my-secret"
        
        sig1 = generate_hmac_signature(payload, secret)
        sig2 = WebhookSecurity.generate_signature(payload, secret)
        
        assert sig1 == sig2


class TestRateLimiter:
    """Test rate limiter"""
    
    def test_allows_under_limit(self):
        """Test requests allowed under limit"""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        
        for i in range(5):
            assert limiter.allow_request("client-1") is True
    
    def test_blocks_over_limit(self):
        """Test requests blocked over limit"""
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        
        # First 3 should pass
        for _ in range(3):
            limiter.allow_request("client-1")
        
        # 4th should be blocked
        assert limiter.allow_request("client-1") is False
    
    def test_different_clients_separate(self):
        """Test different clients have separate limits"""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        
        # Client 1 uses their quota
        limiter.allow_request("client-1")
        limiter.allow_request("client-1")
        assert limiter.allow_request("client-1") is False
        
        # Client 2 still has full quota
        assert limiter.allow_request("client-2") is True
        assert limiter.allow_request("client-2") is True
    
    def test_window_expiry(self):
        """Test requests allowed after window expires"""
        limiter = RateLimiter(max_requests=2, window_seconds=0.1)
        
        # Use up quota
        limiter.allow_request("client-1")
        limiter.allow_request("client-1")
        assert limiter.allow_request("client-1") is False
        
        # Wait for window to expire
        time.sleep(0.15)
        
        # Should be allowed again
        assert limiter.allow_request("client-1") is True
    
    def test_get_remaining(self):
        """Test remaining requests count"""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        
        assert limiter.get_remaining("client-1") == 5
        
        limiter.allow_request("client-1")
        assert limiter.get_remaining("client-1") == 4
        
        limiter.allow_request("client-1")
        assert limiter.get_remaining("client-1") == 3


class TestMockDhanAPI:
    """Test mock Dhan API"""
    
    def test_get_fundlimit(self):
        """Test mock fundlimit API"""
        mock = MockDhanAPI()
        
        result = mock.get_fundlimit()
        
        assert "dhanClientId" in result
        assert "availabelBalance" in result
        assert mock.call_count == 1
    
    def test_place_order(self):
        """Test mock place order API"""
        mock = MockDhanAPI()
        
        result = mock.place_order({"symbol": "RELIANCE", "qty": 10})
        
        assert "orderId" in result
        assert "orderStatus" in result
        assert result["orderStatus"] == "PENDING"
    
    def test_fail_after_n_calls(self):
        """Test mock API failure after N calls"""
        mock = MockDhanAPI(fail_after=2)
        
        # First 2 calls succeed
        mock.get_fundlimit()
        mock.get_fundlimit()
        
        # 3rd call fails
        with pytest.raises(Exception, match="Mock API failure"):
            mock.get_fundlimit()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
