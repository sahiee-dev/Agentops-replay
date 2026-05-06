"""
conftest.py for integration tests.

Provides:
- anyio_backend: pins async tests to asyncio (trio not installed)
- requires_docker: skips DB-dependent tests when Postgres is not reachable
"""

import socket
import pytest


@pytest.fixture(scope="session")
def anyio_backend():
    """Pin anyio to asyncio — trio is not installed in this environment."""
    return "asyncio"


def _postgres_is_reachable(host: str = "localhost", port: int = 5432) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def pytest_collection_modifyitems(config, items):
    db_available = _postgres_is_reachable()
    skip_marker = pytest.mark.skip(
        reason="Requires Docker (Postgres not reachable on localhost:5432). "
               "Run: cd backend && docker-compose up -d"
    )
    for item in items:
        if item.get_closest_marker("requires_docker") and not db_available:
            item.add_marker(skip_marker)

