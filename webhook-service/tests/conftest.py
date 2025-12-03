"""
Pytest configuration and shared fixtures for webhook service tests
"""

import pytest
import sys
import os
from pathlib import Path

# Add parent directory to path so we can import app
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def app():
    """Get the FastAPI app instance"""
    from app import app
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    from fastapi.testclient import TestClient
    return TestClient(app)


@pytest.fixture
def webhook_payload():
    """Sample valid webhook payload"""
    return {
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
        ],
        "metadata": {
            "interval": "1D",
            "time": "2025-12-03 14:30:00",
            "timenow": "2025-12-03 14:31:00"
        }
    }


@pytest.fixture
def webhook_payload_sell():
    """Sample SELL webhook payload"""
    return {
        "alertType": "SELL",
        "order_legs": [
            {
                "symbol": "INFY",
                "exchange": "NSE",
                "transactionType": "SELL",
                "quantity": 100,
                "orderType": "MARKET",
                "productType": "MIS",
                "price": 0
            }
        ],
        "metadata": {
            "interval": "1D",
            "time": "2025-12-03 14:30:00",
            "timenow": "2025-12-03 14:31:00"
        }
    }


@pytest.fixture
def webhook_payload_multi_leg():
    """Sample multi-leg webhook payload"""
    return {
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
            },
            {
                "symbol": "TCS",
                "exchange": "NSE",
                "transactionType": "BUY",
                "quantity": 50,
                "orderType": "MARKET",
                "productType": "MIS",
                "price": 0
            }
        ],
        "metadata": {
            "interval": "1D",
            "time": "2025-12-03 14:30:00",
            "timenow": "2025-12-03 14:31:00"
        }
    }


@pytest.fixture
def mock_dhan_client(mocker):
    """Mock Dhan client"""
    mock = mocker.MagicMock()
    mock.get_security_id.return_value = "123456"
    mock.check_available_quantity.return_value = {
        "available": True,
        "available_quantity": 1000,
        "required_quantity": 100,
        "source": "portfolio"
    }
    mock.place_order.return_value = {
        "status": "success",
        "order_id": "12345",
        "message": "Order placed successfully"
    }
    return mock


@pytest.fixture
def mock_telegram(mocker):
    """Mock Telegram notifier"""
    mock = mocker.MagicMock()
    mock.enabled = True
    mock.notify_alert_received = mocker.AsyncMock()
    mock.notify_order_result = mocker.AsyncMock()
    return mock


def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "requires_firestore: mark test as requiring Firestore"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection"""
    for item in items:
        # Add markers based on test name/path
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        if "firestore" in item.nodeid.lower():
            item.add_marker(pytest.mark.requires_firestore)
        if "slow" in item.nodeid.lower():
            item.add_marker(pytest.mark.slow)
