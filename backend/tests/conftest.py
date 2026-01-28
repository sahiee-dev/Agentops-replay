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
    """
    Set up a fresh test database schema for the test session and remove it afterward.
    
    This fixture ensures the database schema is recreated before tests run by dropping all existing tables and creating them from the metadata, yields control to tests, and drops all tables again after the test session completes. Intended to be used as a session-scoped, autouse pytest fixture to provide a clean schema for the entire test session.
    """
    # Drop all tables
    Base.metadata.drop_all(bind=engine)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    yield
    
    # Cleanup
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_tables():
    """
    Truncate specific database tables to provide a clean state before each test.
    
    This fixture clears the `chain_seals`, `event_chains`, and `sessions` tables and commits the transaction, ensuring tests run against an empty set of rows. It yields control to the test and closes the database session afterwards.
    """
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
    
    yield
