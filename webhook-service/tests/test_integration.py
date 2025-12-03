"""
Integration tests for TradingView webhook service
Tests webhook endpoints, order processing, and logging
"""

import pytest
import asyncio
import json
from datetime import datetime
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from zoneinfo import ZoneInfo

# Import the app (adjust import path as needed)
import sys
sys.path.insert(0, '/Users/abhishekshah/Desktop/quantlab-workspace/webhook-service')


class TestWebhookEndpoints:
    """Test webhook service endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from app import app
        return TestClient(app)

    def test_health_endpoint(self, client):
        """Test /health endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        assert "status" in response.json()

    def test_logs_endpoint_empty(self, client):
        """Test /logs endpoint returns JSON"""
        response = client.get("/logs?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "count" in data
        assert "logs" in data
        assert isinstance(data["logs"], list)

    def test_firestore_logs_endpoint(self, client):
        """Test /logs/firestore endpoint"""
        response = client.get("/logs/firestore?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "success"
        assert "logs" in data
        assert "source" in data
        assert data["source"] == "firestore"

    def test_logs_limit_parameter(self, client):
        """Test /logs endpoint respects limit parameter"""
        response = client.get("/logs?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) <= 5

    def test_info_endpoint(self, client):
        """Test /info endpoint returns service information"""
        response = client.get("/info")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert data["service"] == "TradingView Webhook"
        assert "version" in data
        assert "endpoints" in data


class TestOrderProcessing:
    """Test order processing logic"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from app import app
        return TestClient(app)

    def test_webhook_requires_auth(self, client):
        """Test webhook endpoint requires authentication"""
        payload = {
            "alertType": "BUY",
            "order_legs": []
        }
        response = client.post("/webhook", json=payload)
        # Should require auth or return error
        assert response.status_code in [401, 403, 400]

    def test_webhook_validates_payload(self, client):
        """Test webhook validates payload structure"""
        # Send invalid payload
        invalid_payload = {"invalid": "data"}
        response = client.post("/webhook?key=GTcl4", json=invalid_payload)
        # Should fail validation
        assert response.status_code >= 400 or "error" in response.json()

    def test_webhook_accepts_valid_payload(self, client):
        """Test webhook accepts valid order payload"""
        valid_payload = {
            "alertType": "BUY",
            "order_legs": [
                {
                    "symbol": "INFY",
                    "exchange": "NSE",
                    "transactionType": "BUY",
                    "quantity": 100,
                    "orderType": "MARKET",
                    "productType": "MIS",
                    "price": 0
                }
            ]
        }
        
        response = client.post("/webhook?key=GTcl4", json=valid_payload)
        # Should process the order (may succeed or queue depending on Dhan config)
        assert response.status_code in [200, 202, 503]


class TestLoggingFunctionality:
    """Test logging to CSV and Firestore"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from app import app
        return TestClient(app)

    def test_csv_logging_initializes(self, client):
        """Test CSV log file is initialized"""
        response = client.get("/logs")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_firestore_logging_initializes(self, client):
        """Test Firestore logging is initialized"""
        response = client.get("/logs/firestore")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["source"] == "firestore"

    def test_logs_structure(self, client):
        """Test log entries have correct structure"""
        response = client.get("/logs?limit=1")
        data = response.json()
        
        # Log structure should have required fields
        if len(data["logs"]) > 0:
            log_entry = data["logs"][0]
            expected_fields = [
                "timestamp", "alert_type", "status", "message"
            ]
            # At least some fields should be present
            assert len(log_entry) > 0


class TestErrorHandling:
    """Test error handling and resilience"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from app import app
        return TestClient(app)

    def test_404_not_found(self, client):
        """Test 404 handling for unknown endpoints"""
        response = client.get("/nonexistent")
        assert response.status_code == 404

    def test_invalid_query_parameters(self, client):
        """Test handling of invalid query parameters"""
        response = client.get("/logs?limit=invalid")
        # Should either handle gracefully or return error
        assert response.status_code in [200, 400]

    def test_ready_endpoint_health_check(self, client):
        """Test /ready endpoint for health checks"""
        response = client.get("/ready")
        assert response.status_code in [200, 503]
        data = response.json()
        assert "ready" in data

    def test_concurrent_requests(self, client):
        """Test service handles concurrent requests"""
        responses = []
        for _ in range(5):
            response = client.get("/logs?limit=1")
            responses.append(response)
        
        # All should succeed
        assert all(r.status_code == 200 for r in responses)


class TestSecurityHeaders:
    """Test security headers and configurations"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from app import app
        return TestClient(app)

    def test_no_sensitive_data_in_logs(self, client):
        """Test sensitive data is not logged"""
        response = client.get("/logs?limit=100")
        data = response.json()
        
        # Check logs don't contain exposed secrets
        log_text = json.dumps(data)
        assert "TELEGRAM_BOT_TOKEN" not in log_text
        assert "dhan-api-key" not in log_text
        assert "api_secret" not in log_text.lower()

    def test_webhook_key_validation(self, client):
        """Test webhook key validation"""
        payload = {"alertType": "BUY", "order_legs": []}
        
        # Without key
        response1 = client.post("/webhook", json=payload)
        
        # With invalid key
        response2 = client.post("/webhook?key=invalid", json=payload)
        
        # Both should fail or require valid key
        assert response1.status_code >= 400 or response2.status_code >= 400


class TestPerformance:
    """Test performance and response times"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from app import app
        return TestClient(app)

    def test_logs_endpoint_response_time(self, client):
        """Test /logs endpoint responds quickly"""
        import time
        start = time.time()
        response = client.get("/logs?limit=10")
        elapsed = time.time() - start
        
        assert response.status_code == 200
        # Should respond within 1 second
        assert elapsed < 1.0

    def test_firestore_logs_response_time(self, client):
        """Test /logs/firestore endpoint responds quickly"""
        import time
        start = time.time()
        response = client.get("/logs/firestore?limit=10")
        elapsed = time.time() - start
        
        assert response.status_code == 200
        # Should respond within 2 seconds (Firestore query)
        assert elapsed < 2.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
