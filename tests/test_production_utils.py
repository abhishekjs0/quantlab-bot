#!/usr/bin/env python3
"""
Unit tests for utils/production_utils.py
Tests production utilities: retry, circuit breaker, HMAC, rate limiting
"""

import pytest
import asyncio
import time
import hmac
import hashlib
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.production_utils import (
    retry_with_backoff,
    CircuitBreaker,
    RateLimiter,
    verify_hmac_signature,
    generate_hmac_signature
)


class TestRetryWithBackoff:
    """Test retry decorator"""
    
    def test_successful_call(self):
        """Test successful call without retries"""
        call_count = [0]
        
        @retry_with_backoff(max_retries=3)
        def successful_func():
            call_count[0] += 1
            return "success"
        
        result = successful_func()
        assert result == "success"
        assert call_count[0] == 1
    
    def test_retry_on_failure(self):
        """Test retry after failures"""
        call_count = [0]
        
        @retry_with_backoff(max_retries=3, initial_delay=0.01)
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
        
        @retry_with_backoff(max_retries=2, initial_delay=0.01)
        def always_failing():
            call_count[0] += 1
            raise ValueError("Permanent failure")
        
        with pytest.raises(ValueError):
            always_failing()
        
        assert call_count[0] == 3  # Initial + 2 retries
    
    def test_exponential_backoff(self):
        """Test exponential backoff timing"""
        call_times = []
        
        @retry_with_backoff(max_retries=2, initial_delay=0.1, backoff_factor=2)
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
        assert delay2 > delay1  # Second delay should be longer


class TestCircuitBreaker:
    """Test circuit breaker pattern"""
    
    def test_closed_state(self):
        """Test circuit breaker in closed state"""
        breaker = CircuitBreaker(failure_threshold=3, timeout=1)
        
        assert breaker.state == "closed"
        assert breaker.can_execute()
    
    def test_open_after_failures(self):
        """Test circuit opens after threshold failures"""
        breaker = CircuitBreaker(failure_threshold=3, timeout=60)
        
        # Record failures
        for _ in range(3):
            breaker.record_failure()
        
        assert breaker.state == "open"
        assert not breaker.can_execute()
    
    def test_success_resets_counter(self):
        """Test successful calls reset failure counter"""
        breaker = CircuitBreaker(failure_threshold=3, timeout=60)
        
        # Record some failures
        breaker.record_failure()
        breaker.record_failure()
        
        # Record success
        breaker.record_success()
        
        # Failure counter should reset
        assert breaker._failure_count == 0
        assert breaker.state == "closed"
    
    def test_half_open_state(self):
        """Test circuit transitions to half-open after timeout"""
        breaker = CircuitBreaker(failure_threshold=2, timeout=0.1)
        
        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == "open"
        
        # Wait for timeout
        time.sleep(0.15)
        
        # Should be half-open now
        assert breaker.can_execute()
        breaker._check_state()
        assert breaker.state == "half_open"
    
    def test_recovery_from_half_open(self):
        """Test recovery to closed state from half-open"""
        breaker = CircuitBreaker(failure_threshold=2, timeout=0.1)
        
        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()
        
        # Wait and allow one call
        time.sleep(0.15)
        breaker._check_state()
        
        # Success should close the circuit
        breaker.record_success()
        assert breaker.state == "closed"


class TestRateLimiter:
    """Test rate limiter"""
    
    def test_allows_within_limit(self):
        """Test requests within rate limit are allowed"""
        limiter = RateLimiter(max_requests=5, window_seconds=1)
        
        # Should allow first 5 requests
        for _ in range(5):
            assert limiter.allow_request()
    
    def test_blocks_over_limit(self):
        """Test requests over rate limit are blocked"""
        limiter = RateLimiter(max_requests=3, window_seconds=1)
        
        # First 3 should succeed
        for _ in range(3):
            assert limiter.allow_request()
        
        # 4th should fail
        assert not limiter.allow_request()
    
    def test_window_reset(self):
        """Test rate limit resets after window"""
        limiter = RateLimiter(max_requests=2, window_seconds=0.2)
        
        # Use up limit
        limiter.allow_request()
        limiter.allow_request()
        assert not limiter.allow_request()
        
        # Wait for window to reset
        time.sleep(0.25)
        
        # Should allow again
        assert limiter.allow_request()
    
    def test_wait_time_calculation(self):
        """Test calculation of wait time"""
        limiter = RateLimiter(max_requests=2, window_seconds=1)
        
        # Use up limit
        limiter.allow_request()
        limiter.allow_request()
        
        # Should need to wait
        wait_time = limiter.get_wait_time()
        assert wait_time > 0
        assert wait_time <= 1


class TestHMACSignature:
    """Test HMAC signature generation and verification"""
    
    def test_generate_signature(self):
        """Test HMAC signature generation"""
        secret = "test_secret"
        message = "test_message"
        
        signature = generate_hmac_signature(message, secret)
        
        assert signature is not None
        assert len(signature) > 0
        assert isinstance(signature, str)
    
    def test_verify_valid_signature(self):
        """Test verification of valid signature"""
        secret = "test_secret"
        message = "test_message"
        
        signature = generate_hmac_signature(message, secret)
        
        assert verify_hmac_signature(message, signature, secret)
    
    def test_verify_invalid_signature(self):
        """Test verification of invalid signature"""
        secret = "test_secret"
        message = "test_message"
        
        invalid_signature = "invalid_signature_12345"
        
        assert not verify_hmac_signature(message, invalid_signature, secret)
    
    def test_signature_tampering_detection(self):
        """Test detection of message tampering"""
        secret = "test_secret"
        original_message = "original_message"
        tampered_message = "tampered_message"
        
        signature = generate_hmac_signature(original_message, secret)
        
        # Signature should not match tampered message
        assert not verify_hmac_signature(tampered_message, signature, secret)
    
    def test_different_secrets(self):
        """Test that different secrets produce different signatures"""
        message = "test_message"
        secret1 = "secret1"
        secret2 = "secret2"
        
        sig1 = generate_hmac_signature(message, secret1)
        sig2 = generate_hmac_signature(message, secret2)
        
        assert sig1 != sig2
    
    def test_signature_deterministic(self):
        """Test that signature generation is deterministic"""
        secret = "test_secret"
        message = "test_message"
        
        sig1 = generate_hmac_signature(message, secret)
        sig2 = generate_hmac_signature(message, secret)
        
        assert sig1 == sig2


class TestProductionUtilsIntegration:
    """Integration tests combining multiple utilities"""
    
    def test_retry_with_circuit_breaker(self):
        """Test retry logic with circuit breaker"""
        breaker = CircuitBreaker(failure_threshold=3, timeout=1)
        call_count = [0]
        
        @retry_with_backoff(max_retries=2, initial_delay=0.01)
        def protected_func():
            call_count[0] += 1
            if not breaker.can_execute():
                raise RuntimeError("Circuit breaker open")
            
            if call_count[0] < 2:
                breaker.record_failure()
                raise ValueError("Temporary failure")
            
            breaker.record_success()
            return "success"
        
        result = protected_func()
        assert result == "success"
    
    def test_rate_limited_retries(self):
        """Test retry with rate limiting"""
        limiter = RateLimiter(max_requests=3, window_seconds=0.5)
        attempts = [0]
        
        @retry_with_backoff(max_retries=2, initial_delay=0.01)
        def rate_limited_func():
            attempts[0] += 1
            if not limiter.allow_request():
                raise RuntimeError("Rate limit exceeded")
            return "success"
        
        # Should succeed within rate limit
        result = rate_limited_func()
        assert result == "success"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
