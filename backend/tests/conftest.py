"""Test configuration and fixtures."""

import pytest
import os
import sys

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../verifier'))

# Set test database URL
os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@localhost:5432/agentops_test"

from app.database import Base, engine


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create test database tables before tests."""
    # Drop all tables
    Base.metadata.drop_all(bind=engine)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    yield
    
    # Cleanup
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db():
    """Database session fixture with automatic cleanup."""
    from sqlalchemy import text
    from app.database import SessionLocal
    
    db = SessionLocal()
    try:
        yield db
    finally:
        # Clean up tables in reverse dependency order
        db.execute(text("TRUNCATE TABLE chain_seals CASCADE"))
        db.execute(text("TRUNCATE TABLE event_chains CASCADE"))
        db.execute(text("TRUNCATE TABLE sessions CASCADE"))
        db.commit()
        db.close()
