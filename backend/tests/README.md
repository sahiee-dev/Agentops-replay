# Backend Test Suite

## Running Tests

### Prerequisites

```bash
# Install test dependencies
pip install pytest pytest-cov httpx

# Start test database
docker-compose up -d postgres

# Create test database
createdb agentops_test
```

### Run All Tests

```bash
cd backend
pytest
```

### Run Specific Test Suites

```bash
# Constitutional guarantees only
pytest tests/test_constitutional.py -v

# API tests only
pytest tests/test_api.py -v

# With coverage
pytest --cov=app --cov-report=html
```

## Test Coverage

### Constitutional Guarantees (`test_constitutional.py`)

- ✅ Server-side hash recomputation (ignores SDK hashes)
- ✅ Sequence gap hard rejection with LOG_DROP
- ✅ SESSION_END enforcement at seal time
- ✅ CHAIN_SEAL authority gate (server only)
- ✅ Binary evidence classification (no PARTIAL)
- ✅ Seal idempotency
- ✅ Full AUTHORITATIVE_EVIDENCE flow

### API Tests (`test_api.py`)

- ✅ Session creation (server/SDK authority)
- ✅ Event appending
- ✅ Sequence violation HTTP 409
- ✅ Session sealing
- ✅ Seal without SESSION_END (HTTP 400)
- ✅ Seal SDK session (HTTP 403)
- ✅ JSON export format
- ✅ PDF export generation

## Test Database

Tests use a separate database: `agentops_test`

Schema is created/dropped automatically by pytest fixtures.

## CI/CD

Add to GitHub Actions:

```yaml
- name: Run tests
  run: |
    pip install -r requirements.txt
    pip install pytest pytest-cov
    pytest --cov=app
```
