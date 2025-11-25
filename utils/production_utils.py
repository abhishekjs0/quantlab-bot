"""
Utility functions for error handling, retries, and security.
Critical production-ready components for webhook service and backtesting.
"""

import functools
import time
import hashlib
import hmac
import logging
from typing import Callable, Optional, Any, Type
from datetime import datetime

logger = logging.getLogger(__name__)


# ============================================================================
# ERROR HANDLING & RETRY LOGIC
# ============================================================================

class RetryConfig:
    """Configuration for retry behavior"""
    def __init__(self,
                 max_attempts: int = 3,
                 initial_delay: float = 1.0,
                 max_delay: float = 60.0,
                 exponential_base: float = 2.0,
                 exceptions: tuple = (Exception,)):
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.exceptions = exceptions


def retry_with_backoff(config: Optional[RetryConfig] = None):
    """
    Decorator to retry a function with exponential backoff.
    
    Usage:
        @retry_with_backoff(RetryConfig(max_attempts=5))
        def my_api_call():
            response = requests.get(...)
            return response.json()
    
    Args:
        config: RetryConfig instance (uses defaults if None)
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            attempt = 0
            delay = config.initial_delay
            
            while attempt < config.max_attempts:
                try:
                    return func(*args, **kwargs)
                except config.exceptions as e:
                    attempt += 1
                    
                    if attempt >= config.max_attempts:
                        logger.error(f"❌ {func.__name__} failed after {attempt} attempts: {e}")
                        raise
                    
                    logger.warning(f"⚠️  {func.__name__} attempt {attempt} failed: {e}. Retrying in {delay:.1f}s...")
                    time.sleep(delay)
                    
                    # Exponential backoff
                    delay = min(delay * config.exponential_base, config.max_delay)
            
            raise Exception(f"Retry logic error - should not reach here")
        
        return wrapper
    return decorator


class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascading failures.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests fail immediately
    - HALF_OPEN: Testing if service recovered
    
    Usage:
        breaker = CircuitBreaker(failure_threshold=5, timeout=60)
        
        @breaker.call
        def api_request():
            return requests.get(...)
    """
    
    def __init__(self,
                 failure_threshold: int = 5,
                 timeout: float = 60.0,
                 expected_exception: Type[Exception] = Exception):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func: Callable) -> Callable:
        """Decorator to wrap function with circuit breaker"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            if self.state == "OPEN":
                # Check if timeout expired
                if self.last_failure_time and time.time() - self.last_failure_time > self.timeout:
                    logger.info(f"🔄 Circuit breaker entering HALF_OPEN state for {func.__name__}")
                    self.state = "HALF_OPEN"
                else:
                    raise Exception(f"Circuit breaker OPEN for {func.__name__}")
            
            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except self.expected_exception as e:
                self._on_failure()
                raise
        
        return wrapper
    
    def _on_success(self):
        """Reset circuit breaker on success"""
        if self.state == "HALF_OPEN":
            logger.info("✅ Circuit breaker reset to CLOSED")
        self.failure_count = 0
        self.state = "CLOSED"
    
    def _on_failure(self):
        """Handle failure and potentially open circuit"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            logger.error(f"❌ Circuit breaker OPEN after {self.failure_count} failures")
            self.state = "OPEN"


# ============================================================================
# SECURITY UTILITIES
# ============================================================================

class WebhookSecurity:
    """Security utilities for webhook signature verification"""
    
    @staticmethod
    def generate_signature(payload: str, secret: str) -> str:
        """
        Generate HMAC-SHA256 signature for webhook payload.
        
        Args:
            payload: Webhook payload (JSON string)
            secret: Secret key for HMAC
            
        Returns:
            Hexadecimal signature string
        """
        return hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    @staticmethod
    def verify_signature(payload: str, signature: str, secret: str) -> bool:
        """
        Verify webhook signature.
        
        Args:
            payload: Webhook payload (JSON string)
            signature: Received signature
            secret: Secret key for HMAC
            
        Returns:
            True if signature is valid
        """
        expected_signature = WebhookSecurity.generate_signature(payload, secret)
        return hmac.compare_digest(signature, expected_signature)
    
    @staticmethod
    def generate_api_key(length: int = 32) -> str:
        """
        Generate a random API key.
        
        Args:
            length: Key length in bytes
            
        Returns:
            Hexadecimal API key string
        """
        import secrets
        return secrets.token_hex(length)


class RateLimiter:
    """
    Simple in-memory rate limiter.
    
    Usage:
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        
        if limiter.allow_request(client_id):
            # Process request
        else:
            # Reject request (429 Too Many Requests)
    """
    
    def __init__(self, max_requests: int = 100, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = {}
    
    def allow_request(self, client_id: str) -> bool:
        """
        Check if request is allowed for given client.
        
        Args:
            client_id: Unique identifier for client (IP, user_id, etc.)
            
        Returns:
            True if request is allowed
        """
        now = time.time()
        
        # Initialize client if not exists
        if client_id not in self._requests:
            self._requests[client_id] = []
        
        # Remove old requests outside window
        self._requests[client_id] = [
            req_time for req_time in self._requests[client_id]
            if now - req_time < self.window_seconds
        ]
        
        # Check if limit exceeded
        if len(self._requests[client_id]) >= self.max_requests:
            return False
        
        # Add current request
        self._requests[client_id].append(now)
        return True
    
    def get_remaining(self, client_id: str) -> int:
        """Get remaining requests for client"""
        if client_id not in self._requests:
            return self.max_requests
        
        now = time.time()
        recent_requests = [
            req_time for req_time in self._requests[client_id]
            if now - req_time < self.window_seconds
        ]
        return max(0, self.max_requests - len(recent_requests))


# ============================================================================
# TESTING UTILITIES
# ============================================================================

class MockDhanAPI:
    """Mock Dhan API for testing without hitting real API"""
    
    def __init__(self, fail_after: Optional[int] = None):
        """
        Args:
            fail_after: Number of successful calls before starting to fail
        """
        self.call_count = 0
        self.fail_after = fail_after
    
    def get_fundlimit(self) -> dict:
        """Mock fundlimit API call"""
        self.call_count += 1
        
        if self.fail_after and self.call_count > self.fail_after:
            raise Exception("Mock API failure")
        
        return {
            "dhanClientId": "1108351648",
            "availabelBalance": 131919.69,
            "sodLimit": 120438.32,
            "collateralAmount": 0.0,
            "receiveableAmount": 0.0,
            "utilizedAmount": 83.0,
            "blockedPayoutAmount": 0.0,
            "withdrawableBalance": 120254.69
        }
    
    def place_order(self, order_data: dict) -> dict:
        """Mock place order API call"""
        self.call_count += 1
        
        if self.fail_after and self.call_count > self.fail_after:
            raise Exception("Mock API failure")
        
        return {
            "orderId": f"MOCK{self.call_count:06d}",
            "orderStatus": "PENDING",
            "timestamp": datetime.now().isoformat()
        }


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # 1. Retry with backoff
    print("\n=== Testing Retry with Backoff ===")
    
    attempt_count = 0
    
    @retry_with_backoff(RetryConfig(max_attempts=3, initial_delay=0.5))
    def flaky_function():
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 3:
            raise Exception(f"Simulated failure {attempt_count}")
        return "Success!"
    
    try:
        result = flaky_function()
        print(f"✅ Result: {result} (after {attempt_count} attempts)")
    except Exception as e:
        print(f"❌ Failed: {e}")
    
    # 2. Circuit breaker
    print("\n=== Testing Circuit Breaker ===")
    
    breaker = CircuitBreaker(failure_threshold=3, timeout=2.0)
    fail_count = 0
    
    @breaker.call
    def unreliable_api():
        nonlocal fail_count
        fail_count += 1
        if fail_count <= 3:
            raise Exception("Service unavailable")
        return "Success"
    
    for i in range(6):
        try:
            result = unreliable_api()
            print(f"✅ Call {i+1}: {result}")
        except Exception as e:
            print(f"❌ Call {i+1}: {e}")
        time.sleep(0.5)
    
    # 3. Webhook signature
    print("\n=== Testing Webhook Security ===")
    
    payload = '{"alert": "BUY", "symbol": "RELIANCE"}'
    secret = "my-webhook-secret"
    
    signature = WebhookSecurity.generate_signature(payload, secret)
    print(f"Signature: {signature[:32]}...")
    
    is_valid = WebhookSecurity.verify_signature(payload, signature, secret)
    print(f"Verification: {'✅ Valid' if is_valid else '❌ Invalid'}")
    
    # 4. Rate limiter
    print("\n=== Testing Rate Limiter ===")
    
    limiter = RateLimiter(max_requests=5, window_seconds=2.0)
    
    for i in range(8):
        allowed = limiter.allow_request("client-1")
        remaining = limiter.get_remaining("client-1")
        print(f"Request {i+1}: {'✅ Allowed' if allowed else '❌ Blocked'} (remaining: {remaining})")
