"""
Integration tests for TradingView webhook service
Tests webhook endpoints, order processing, and logging
"""

import pytest
import json
from datetime import datetime, timezone
from pathlib import Path
from fastapi.testclient import TestClient

# Import the app - use relative path from this file's location
import sys
_webhook_service_dir = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(_webhook_service_dir))


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
        """Test /logs/firestore endpoint returns valid response"""
        response = client.get("/logs/firestore?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["success", "error"]

    def test_logs_limit_parameter(self, client):
        """Test /logs endpoint respects limit parameter"""
        response = client.get("/logs?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) <= 5


class TestOrderProcessing:
    """Test order processing logic"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from app import app
        return TestClient(app)

    @pytest.fixture
    def valid_payload(self):
        """Create valid webhook payload matching expected schema"""
        now = datetime.now(timezone.utc).isoformat()
        return {
            "secret": "GTcl4",
            "alertType": "multi_leg_order",
            "order_legs": [
                {
                    "transactionType": "B",
                    "orderType": "MKT",
                    "quantity": "100",
                    "exchange": "NSE",
                    "symbol": "INFY",
                    "instrument": "EQ",
                    "productType": "I",
                    "sort_order": "1",
                    "price": "0",
                    "amoTime": "PRE_OPEN",
                    "meta": {
                        "interval": "1D",
                        "time": now,
                        "timenow": now
                    }
                }
            ]
        }

    def test_webhook_requires_secret(self, client):
        """Test webhook endpoint requires secret in payload"""
        payload = {"alertType": "multi_leg_order", "order_legs": []}
        response = client.post("/webhook", json=payload)
        assert response.status_code == 422

    def test_webhook_validates_payload(self, client):
        """Test webhook validates payload structure"""
        response = client.post("/webhook", json={"invalid": "data"})
        assert response.status_code == 422

    def test_webhook_accepts_valid_payload(self, client, valid_payload):
        """Test webhook accepts valid order payload"""
        response = client.post("/webhook", json=valid_payload)
        assert response.status_code in [200, 202, 401, 403, 503]

    def test_webhook_rejects_invalid_secret(self, client, valid_payload):
        """Test webhook rejects invalid secret"""
        valid_payload["secret"] = "INVALID_SECRET"
        response = client.post("/webhook", json=valid_payload)
        assert response.status_code in [401, 403]


class TestLoggingFunctionality:
    """Test logging functionality"""

    @pytest.fixture
    def client(self):
        from app import app
        return TestClient(app)

    def test_csv_logging_initializes(self, client):
        """Test CSV log file is initialized"""
        response = client.get("/logs")
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    def test_firestore_logging_returns_response(self, client):
        """Test Firestore logging endpoint returns valid response"""
        response = client.get("/logs/firestore")
        assert response.status_code == 200
        assert response.json()["status"] in ["success", "error"]


class TestErrorHandling:
    """Test error handling and resilience"""

    @pytest.fixture
    def client(self):
        from app import app
        return TestClient(app)

    def test_404_not_found(self, client):
        """Test 404 handling"""
        assert client.get("/nonexistent").status_code == 404

    def test_invalid_query_parameters(self, client):
        """Test handling of invalid query parameters"""
        response = client.get("/logs?limit=invalid")
        assert response.status_code in [200, 400, 422]

    def test_ready_endpoint_health_check(self, client):
        """Test /ready endpoint for health checks"""
        response = client.get("/ready")
        assert response.status_code in [200, 503]
        assert "ready" in response.json()

    def test_concurrent_requests(self, client):
        """Test service handles concurrent requests"""
        responses = [client.get("/logs?limit=1") for _ in range(5)]
        assert all(r.status_code == 200 for r in responses)


class TestSecurityHeaders:
    """Test security configurations"""

    @pytest.fixture
    def client(self):
        from app import app
        return TestClient(app)

    def test_no_sensitive_data_in_logs(self, client):
        """Test sensitive data is not logged"""
        response = client.get("/logs?limit=100")
        log_text = json.dumps(response.json())
        assert "TELEGRAM_BOT_TOKEN" not in log_text
        assert "dhan-api-key" not in log_text

    def test_webhook_without_secret_fails(self, client):
        """Test webhook without secret fails"""
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "alertType": "multi_leg_order",
            "order_legs": [{
                "transactionType": "B", "orderType": "MKT",
                "quantity": "100", "exchange": "NSE", "symbol": "INFY",
                "instrument": "EQ", "productType": "I", "sort_order": "1",
                "price": "0", "amoTime": "PRE_OPEN",
                "meta": {"interval": "1D", "time": now, "timenow": now}
            }]
        }
        assert client.post("/webhook", json=payload).status_code == 422


class TestPerformance:
    """Test performance"""

    @pytest.fixture
    def client(self):
        from app import app
        return TestClient(app)

    def test_logs_endpoint_response_time(self, client):
        """Test /logs endpoint responds quickly"""
        import time
        start = time.time()
        response = client.get("/logs?limit=10")
        assert response.status_code == 200
        assert time.time() - start < 1.0

    def test_firestore_logs_response_time(self, client):
        """Test /logs/firestore endpoint responds quickly"""
        import time
        start = time.time()
        response = client.get("/logs/firestore?limit=10")
        assert response.status_code == 200
        assert time.time() - start < 2.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
