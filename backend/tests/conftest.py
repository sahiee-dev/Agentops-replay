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


@pytest.fixture(autouse=True)
def clean_tables():
    """Clean tables between tests."""
    from app.database import SessionLocal
    
    db = SessionLocal()
    try:
        # Clear all tables (but don't drop schema)
        db.execute("TRUNCATE TABLE chain_seals CASCADE")
        db.execute("TRUNCATE TABLE event_chains CASCADE")
        db.execute("TRUNCATE TABLE sessions CASCADE")
        db.commit()
    finally:
        db.close()
    
    yield
