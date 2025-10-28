"""
Unit tests for get_audit_log handler.
"""
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.database.models import AuditLog, Base
from app.usecases.queries.get_audit_log.handler import get_audit_log_handler
from app.usecases.queries.get_audit_log.types import GetAuditLogInput


@pytest.fixture
def in_memory_session() -> Session:
    """Create an in-memory SQLite session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def sample_audit_logs(in_memory_session: Session) -> list[AuditLog]:
    """Create sample audit logs for testing."""
    from datetime import datetime, timedelta

    base_time = datetime.utcnow()

    logs = [
        AuditLog(
            user="user1",
            action="create_trial",
            entity="trial",
            entity_id="123",
            payload_json=json.dumps({"name": "Trial A"}),
            created_at=base_time,
        ),
        AuditLog(
            user="user2",
            action="update_trial_metadata",
            entity="trial",
            entity_id="123",
            payload_json=json.dumps({"phase": "Phase II"}),
            created_at=base_time + timedelta(seconds=1),
        ),
        AuditLog(
            user="user1",
            action="register_site",
            entity="trial",
            entity_id="123",
            payload_json=json.dumps({"site_id": 456}),
            created_at=base_time + timedelta(seconds=2),
        ),
        # Different entity
        AuditLog(
            user="user3",
            action="create_trial",
            entity="trial",
            entity_id="456",
            payload_json=json.dumps({"name": "Trial B"}),
            created_at=base_time + timedelta(seconds=3),
        ),
        # Different entity type
        AuditLog(
            user="user1",
            action="register_site",
            entity="site",
            entity_id="789",
            payload_json=json.dumps({"name": "Site X"}),
            created_at=base_time + timedelta(seconds=4),
        ),
    ]
    in_memory_session.add_all(logs)
    in_memory_session.commit()
    return logs


def test_get_audit_log_for_entity(
    in_memory_session: Session, sample_audit_logs: list[AuditLog]
) -> None:
    """Test retrieving audit logs for a specific entity."""
    input_data = GetAuditLogInput(entity="trial", entity_id="123")
    result = get_audit_log_handler(in_memory_session, input_data)

    # Should return 3 entries for trial 123
    assert len(result.entries) == 3

    # Verify all entries are for the correct entity
    assert all(entry.entity == "trial" for entry in result.entries)
    assert all(entry.entity_id == "123" for entry in result.entries)

    # Verify ordering (most recent first)
    # Last added should be first (register_site)
    assert result.entries[0].action == "register_site"
    assert result.entries[1].action == "update_trial_metadata"
    assert result.entries[2].action == "create_trial"


def test_get_audit_log_different_entity(
    in_memory_session: Session, sample_audit_logs: list[AuditLog]
) -> None:
    """Test retrieving audit logs for a different entity."""
    input_data = GetAuditLogInput(entity="trial", entity_id="456")
    result = get_audit_log_handler(in_memory_session, input_data)

    assert len(result.entries) == 1
    assert result.entries[0].entity_id == "456"
    assert result.entries[0].action == "create_trial"


def test_get_audit_log_different_entity_type(
    in_memory_session: Session, sample_audit_logs: list[AuditLog]
) -> None:
    """Test retrieving audit logs for a different entity type."""
    input_data = GetAuditLogInput(entity="site", entity_id="789")
    result = get_audit_log_handler(in_memory_session, input_data)

    assert len(result.entries) == 1
    assert result.entries[0].entity == "site"
    assert result.entries[0].entity_id == "789"


def test_get_audit_log_no_entries(in_memory_session: Session) -> None:
    """Test retrieving audit logs when none exist."""
    input_data = GetAuditLogInput(entity="trial", entity_id="999")
    result = get_audit_log_handler(in_memory_session, input_data)

    assert len(result.entries) == 0


def test_get_audit_log_with_limit(
    in_memory_session: Session, sample_audit_logs: list[AuditLog]
) -> None:
    """Test limiting the number of audit log entries returned."""
    input_data = GetAuditLogInput(entity="trial", entity_id="123", limit=2)
    result = get_audit_log_handler(in_memory_session, input_data)

    # Should return only 2 entries (most recent)
    assert len(result.entries) == 2
    # Verify the entries are for trial 123
    assert all(e.entity_id == "123" for e in result.entries)
    # Verify they're sorted by created_at desc
    assert result.entries[0].created_at >= result.entries[1].created_at


def test_get_audit_log_payload_content(
    in_memory_session: Session, sample_audit_logs: list[AuditLog]
) -> None:
    """Test that payload JSON is correctly retrieved."""
    input_data = GetAuditLogInput(entity="trial", entity_id="123")
    result = get_audit_log_handler(in_memory_session, input_data)

    # Find create_trial action
    create_entry = next(e for e in result.entries if e.action == "create_trial")
    assert create_entry.payload_json is not None
    payload = json.loads(create_entry.payload_json)
    assert payload["name"] == "Trial A"


def test_get_audit_log_user_info(
    in_memory_session: Session, sample_audit_logs: list[AuditLog]
) -> None:
    """Test that user information is correctly retrieved."""
    input_data = GetAuditLogInput(entity="trial", entity_id="123")
    result = get_audit_log_handler(in_memory_session, input_data)

    # Verify user information
    users = {entry.user for entry in result.entries}
    assert users == {"user1", "user2"}


def test_get_audit_log_ordering(
    in_memory_session: Session, sample_audit_logs: list[AuditLog]
) -> None:
    """Test that audit logs are ordered by created_at descending."""
    input_data = GetAuditLogInput(entity="trial", entity_id="123")
    result = get_audit_log_handler(in_memory_session, input_data)

    # Verify descending order
    for i in range(len(result.entries) - 1):
        assert result.entries[i].created_at >= result.entries[i + 1].created_at
