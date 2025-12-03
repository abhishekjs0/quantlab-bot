# Testing Guide - TradingView Webhook Service

## Overview

This document describes the automated testing setup for the TradingView webhook service deployed on Google Cloud Run.

## Test Structure

```
webhook-service/
├── tests/
│   ├── __init__.py              # Tests package
│   ├── conftest.py              # Pytest fixtures and configuration
│   └── test_integration.py       # Integration tests
├── pytest.ini                    # Pytest configuration
└── requirements-dev.txt          # Testing dependencies
```

## Running Tests

### Prerequisites

```bash
# Install test dependencies
pip install -r requirements-dev.txt
```

### Run All Tests

```bash
# Run all tests with verbose output
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=. --cov-report=html

# Run specific test file
pytest tests/test_integration.py -v

# Run specific test class
pytest tests/test_integration.py::TestWebhookEndpoints -v

# Run specific test
pytest tests/test_integration.py::TestWebhookEndpoints::test_health_endpoint -v
```

### Test Categories

Tests are organized by marker for easier filtering:

```bash
# Run only integration tests
pytest tests/ -m integration -v

# Run only unit tests
pytest tests/ -m unit -v

# Run smoke tests (quick validation)
pytest tests/ -m smoke -v

# Run tests requiring Firestore
pytest tests/ -m requires_firestore -v

# Exclude slow tests
pytest tests/ -m "not slow" -v
```

## Test Coverage

### TestWebhookEndpoints (9 tests)
- ✅ Health endpoint functionality
- ✅ CSV logs endpoint response
- ✅ Firestore logs endpoint response
- ✅ Logs limit parameter handling
- ✅ Service info endpoint
- ✅ Concurrent request handling
- ✅ Security headers validation
- ✅ Invalid query parameter handling
- ✅ Ready/health check endpoint

### TestOrderProcessing (3 tests)
- ✅ Webhook authentication requirement
- ✅ Payload validation
- ✅ Valid order acceptance

### TestLoggingFunctionality (3 tests)
- ✅ CSV logging initialization
- ✅ Firestore logging initialization
- ✅ Log entry structure validation

### TestErrorHandling (4 tests)
- ✅ 404 error handling
- ✅ Invalid parameter handling
- ✅ Health check endpoint
- ✅ Concurrent request handling

### TestSecurityHeaders (2 tests)
- ✅ No sensitive data in logs
- ✅ Webhook key validation

### TestPerformance (2 tests)
- ✅ CSV logs endpoint response time (<1s)
- ✅ Firestore logs endpoint response time (<2s)

**Total: 23 Integration Tests**

## GitHub Actions CI/CD Pipeline

Automated testing and deployment is configured in `.github/workflows/deploy-webhook.yml`:

### Workflow Steps

1. **Checkout Code**: Clone repository
2. **Google Cloud Authentication**: Use Workload Identity Federation
3. **Setup gcloud**: Initialize Google Cloud SDK
4. **Configure Docker**: Setup Artifact Registry access
5. **Run Integration Tests**: Execute pytest suite
6. **Build & Deploy**: Deploy to Cloud Run if tests pass
7. **Verify Deployment**: Test the deployed service
8. **Notify**: Report success/failure

### Deployment Triggers

- ✅ Push to `main` branch
- ✅ Changes to `webhook-service/**`
- ✅ Manual workflow dispatch (`workflow_dispatch`)

### Prerequisites for GitHub Actions

To enable automated deployments, set up these secrets in your GitHub repository:

```
WIF_PROVIDER         # Workload Identity Federation provider
WIF_SERVICE_ACCOUNT  # Google Cloud service account email
```

**Setup Instructions**:
```bash
# 1. Create service account
gcloud iam service-accounts create github-actions \
  --display-name="GitHub Actions Deployer"

# 2. Grant necessary roles
gcloud projects add-iam-policy-binding tradingview-webhook-prod \
  --member="serviceAccount:github-actions@tradingview-webhook-prod.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding tradingview-webhook-prod \
  --member="serviceAccount:github-actions@tradingview-webhook-prod.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

# 3. Set up Workload Identity Federation
# (Follow Google Cloud documentation for your GitHub repository)

# 4. Add secrets to GitHub repository settings
```

## Local Development Testing

### Before Committing

```bash
# Run full test suite
pytest tests/ -v

# Check code coverage
pytest tests/ --cov=webhook_service --cov-report=term-missing

# Run only fast tests
pytest tests/ -m "not slow" -v

# Check for security issues
pytest tests/ -m "requires_secrets" -v --tb=short
```

### Integration Testing Against Local Service

```bash
# Start webhook service locally
python -m uvicorn app:app --reload

# In another terminal, run tests
pytest tests/ -v

# Run against deployed service
export WEBHOOK_URL="https://your-deployed-service.run.app"
pytest tests/ -v
```

## Continuous Integration

### Test Reports

Tests produce:
- Console output (detailed during development)
- Coverage report (HTML in `htmlcov/` directory)
- JUnit XML report (for CI integrations)

### Failure Handling

If tests fail in the CI pipeline:

1. **Read Error Message**: Detailed error output shows what failed
2. **Check Logs**: View full logs in GitHub Actions
3. **Run Locally**: Reproduce the failure locally with same conditions
4. **Fix Code**: Make necessary changes
5. **Re-run Tests**: Verify fix before pushing

### Rollback on Failure

If deployment fails:
1. Previous revision remains active (automatic)
2. Fix issues locally
3. Run tests to verify
4. Push to trigger new deployment

## Test Maintenance

### When to Add Tests

- ✅ Adding new endpoint
- ✅ Changing order processing logic
- ✅ Updating authentication/authorization
- ✅ Modifying logging functionality
- ✅ Fixing a bug (add test to prevent regression)

### Test Best Practices

1. **Descriptive Names**: Test names should clearly describe what is tested
   ```python
   def test_firestore_logs_endpoint_accepts_limit_parameter(self, client):
   ```

2. **One Assertion Per Test**: Each test should verify one behavior
   ```python
   # Good
   def test_logs_returns_json(self, client):
       response = client.get("/logs")
       assert isinstance(response.json(), dict)
   
   # Avoid
   def test_logs(self, client):  # Too vague
       response = client.get("/logs")
       assert response.status_code == 200
       assert "logs" in response.json()
       assert isinstance(response.json()["logs"], list)
   ```

3. **Use Fixtures**: Reuse common setup via fixtures
   ```python
   # Good
   def test_something(self, client, webhook_payload):
       response = client.post("/webhook?key=GTcl4", json=webhook_payload)
   ```

4. **Mock External Dependencies**: Don't call real APIs in tests
   ```python
   # Good
   def test_order_processing(self, mock_dhan_client):
       mock_dhan_client.place_order.return_value = {"status": "success"}
   ```

## Performance Testing

Current performance benchmarks:

| Endpoint | Target | Current | Status |
|----------|--------|---------|--------|
| /logs | <1s | <200ms | ✅ Pass |
| /logs/firestore | <2s | <500ms | ✅ Pass |
| /health | <500ms | <100ms | ✅ Pass |
| /webhook (validation) | <100ms | <50ms | ✅ Pass |

Run performance tests:
```bash
pytest tests/test_integration.py::TestPerformance -v
```

## Debugging Failed Tests

### Increase Verbosity

```bash
# Very verbose output with full tracebacks
pytest tests/ -vv --tb=long

# Show print statements
pytest tests/ -v -s

# Only show failed tests
pytest tests/ --tb=short --lf
```

### Run with Debugging

```bash
# Drop into debugger on failure
pytest tests/ --pdb

# Drop into debugger on error
pytest tests/ --pdbcls=IPython.terminal.debugger:TerminalPdb

# Stop on first failure
pytest tests/ -x
```

### Inspect Test State

```python
# Add breakpoints in test code
def test_something(self, client):
    response = client.get("/logs")
    breakpoint()  # Execution will pause here
    assert response.status_code == 200
```

## Monitoring in Production

After deployment, monitor test-related metrics:

```bash
# View Cloud Run logs
gcloud run services logs read tradingview-webhook --region=asia-south1

# Check for errors
gcloud run services logs read tradingview-webhook \
  --region=asia-south1 | grep -i error

# View metrics
gcloud monitoring dashboards list
```

## Troubleshooting

### Tests Pass Locally But Fail in CI

**Causes**:
- Different Python version
- Missing environment variables
- Firestore not available in test environment
- Timing-related issues

**Solutions**:
- Check CI environment matches local
- Ensure all required secrets are configured
- Mock Firestore in CI tests
- Increase test timeouts for CI

### Firestore Tests Timeout

**Cause**: Firestore not initialized or slow network

**Solution**:
```bash
# Skip Firestore tests if needed
pytest tests/ -m "not requires_firestore" -v
```

### GitHub Actions Deployment Fails

**Check**:
1. Service account has correct permissions
2. Workload Identity Federation is configured
3. Cloud Run API is enabled
4. Integration tests pass

**Debug**:
```bash
# View GitHub Actions logs
# Go to: Repository → Actions → Latest run → Show logs
```

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Google Cloud Run Testing](https://cloud.google.com/run/docs/testing/test-overview)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Firestore Testing](https://firebase.google.com/docs/firestore/solutions/emulator-setup)

