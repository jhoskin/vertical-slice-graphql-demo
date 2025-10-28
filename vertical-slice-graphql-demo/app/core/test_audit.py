"""
Unit tests for audit decorator.
"""
from dataclasses import dataclass

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.audit import audited
from app.infrastructure.database.models import AuditLog, Base


@dataclass
class MockResult:
    """Mock result object for testing."""
    id: int
    name: str
    status: str


@pytest.fixture
def in_memory_session() -> Session:
    """Create an in-memory SQLite session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


def test_audited_decorator_success(in_memory_session: Session) -> None:
    """Test that audit log is created on successful command."""

    @audited(action="test_action", entity="test_entity", user="test_user")
    def mock_handler(session: Session, data: dict) -> MockResult:
        return MockResult(id=123, name="Test", status="active")

    # Execute handler
    result = mock_handler(in_memory_session, {"test": "data"})

    # Verify result
    assert result.id == 123
    assert result.name == "Test"

    # Verify audit log was created
    audit_logs = in_memory_session.query(AuditLog).all()
    assert len(audit_logs) == 1
    assert audit_logs[0].action == "test_action"
    assert audit_logs[0].entity == "test_entity"
    assert audit_logs[0].entity_id == "123"
    assert audit_logs[0].user == "test_user"
    assert '"id": 123' in audit_logs[0].payload_json
    assert '"name": "Test"' in audit_logs[0].payload_json


def test_audited_decorator_custom_entity_id_fn(in_memory_session: Session) -> None:
    """Test audit decorator with custom entity_id extraction."""

    @audited(
        action="test_action",
        entity="test_entity",
        entity_id_fn=lambda r: f"custom_{r.id}",
    )
    def mock_handler(session: Session) -> MockResult:
        return MockResult(id=456, name="Custom", status="active")

    # Execute handler
    mock_handler(in_memory_session)

    # Verify custom entity_id
    audit_logs = in_memory_session.query(AuditLog).all()
    assert len(audit_logs) == 1
    assert audit_logs[0].entity_id == "custom_456"


def test_audited_decorator_failure(in_memory_session: Session) -> None:
    """Test that audit log is created on command failure."""

    @audited(action="test_action", entity="test_entity")
    def failing_handler(session: Session) -> MockResult:
        raise ValueError("Something went wrong")

    # Execute handler and expect exception
    with pytest.raises(ValueError, match="Something went wrong"):
        failing_handler(in_memory_session)

    # Verify error audit log was created
    audit_logs = in_memory_session.query(AuditLog).all()
    assert len(audit_logs) == 1
    assert audit_logs[0].action == "test_action_failed"
    assert audit_logs[0].entity_id == "error"
    assert "Something went wrong" in audit_logs[0].payload_json
    assert "ValueError" in audit_logs[0].payload_json


def test_audited_decorator_default_user(in_memory_session: Session) -> None:
    """Test that default user is 'system'."""

    @audited(action="test_action", entity="test_entity")
    def mock_handler(session: Session) -> MockResult:
        return MockResult(id=789, name="Default User", status="active")

    # Execute handler
    mock_handler(in_memory_session)

    # Verify default user
    audit_logs = in_memory_session.query(AuditLog).all()
    assert len(audit_logs) == 1
    assert audit_logs[0].user == "system"


def test_audited_decorator_no_session(in_memory_session: Session) -> None:
    """Test that decorator handles missing session gracefully."""

    @audited(action="test_action", entity="test_entity")
    def mock_handler_no_session(data: dict) -> MockResult:
        return MockResult(id=999, name="No Session", status="active")

    # Execute handler without session as first arg
    result = mock_handler_no_session({"test": "data"})

    # Should still return result but no audit log
    assert result.id == 999
    audit_logs = in_memory_session.query(AuditLog).all()
    assert len(audit_logs) == 0
