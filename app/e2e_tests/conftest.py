"""
Pytest configuration for E2E tests.

This module provides fixtures for testing the complete application
via GraphQL using an ASGI test client.

Note: These E2E tests use a test database file (test_e2e.db) that is
cleaned between tests. This is more realistic than mocking the database
layer, as it tests the actual database operations end-to-end.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.infrastructure.database.models import Base
from app.main import app


@pytest.fixture(scope="function")
def test_client():
    """
    Create a test client with a clean test database.

    Each test gets a fresh database by dropping and recreating all tables.
    """
    # Use a dedicated test database file
    test_db_path = Path("test_e2e.db")

    # Create engine for test database
    engine = create_engine(
        f"sqlite:///{test_db_path}",
        connect_args={"check_same_thread": False}
    )

    # Drop all tables and recreate (ensures clean state)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    # Update the app's session engine temporarily
    from app.infrastructure.database import session as session_module
    original_engine = session_module.engine
    original_session_local = session_module.SessionLocal

    # Monkey-patch for this test
    session_module.engine = engine
    from sqlalchemy.orm import sessionmaker
    session_module.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with TestClient(app) as client:
        yield client

    # Restore original engine
    session_module.engine = original_engine
    session_module.SessionLocal = original_session_local

    # Cleanup test database file
    try:
        test_db_path.unlink()
    except Exception:
        pass


@pytest.fixture
def graphql_client(test_client):
    """
    Create a helper for making GraphQL requests.

    Returns a callable that sends GraphQL queries/mutations.
    """
    def _query(query: str, variables: dict = None):
        """Execute a GraphQL query or mutation."""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        response = test_client.post("/graphql", json=payload)
        return response.json()

    return _query
