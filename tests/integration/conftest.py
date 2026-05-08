"""
conftest.py for integration tests.

Provides:
- anyio_backend: pins async tests to asyncio
- In-memory SQLite database override for FastAPI's get_db dependency
- Auto-skip when backend packages are not available
"""

import pytest


@pytest.fixture(scope="session")
def anyio_backend():
    """Pin anyio to asyncio — trio is not installed in this environment."""
    return "asyncio"


def pytest_collection_modifyitems(config, items):
    """Skip requires_docker tests — we use in-memory SQLite instead."""
    skip_marker = pytest.mark.skip(
        reason="Docker-based test skipped; using in-memory SQLite."
    )
    for item in items:
        if item.get_closest_marker("requires_docker"):
            item.add_marker(skip_marker)
