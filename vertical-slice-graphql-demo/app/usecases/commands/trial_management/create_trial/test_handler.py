"""
Unit tests for create_trial handler.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.database.models import AuditLog, Base, Trial
from app.usecases.commands.trial_management._validation import ValidationError
from app.usecases.commands.trial_management.create_trial.handler import create_trial_handler
from app.usecases.commands.trial_management.create_trial.types import CreateTrialInput


@pytest.fixture
def in_memory_session() -> Session:
    """Create an in-memory SQLite session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


def test_create_trial_success(in_memory_session: Session) -> None:
    """Test successful trial creation."""
    input_data = CreateTrialInput(name="Test Trial", phase="Phase I")

    result = create_trial_handler(in_memory_session, input_data)

    # Verify result
    assert result.id is not None
    assert result.name == "Test Trial"
    assert result.phase == "Phase I"
    assert result.status == "draft"
    assert result.created_at is not None

    # Verify trial was created in database
    trial = in_memory_session.query(Trial).filter_by(id=result.id).first()
    assert trial is not None
    assert trial.name == "Test Trial"
    assert trial.status == "draft"

    # Verify audit log was created
    audit_logs = in_memory_session.query(AuditLog).all()
    assert len(audit_logs) == 1
    assert audit_logs[0].action == "create_trial"
    assert audit_logs[0].entity == "trial"
    assert audit_logs[0].entity_id == str(result.id)


def test_create_trial_with_different_phases(in_memory_session: Session) -> None:
    """Test creating trials with various valid phases."""
    phases = ["Phase I", "Phase II", "Phase III", "Phase IV", "Preclinical"]

    for phase in phases:
        input_data = CreateTrialInput(name=f"Trial {phase}", phase=phase)
        result = create_trial_handler(in_memory_session, input_data)
        assert result.phase == phase


def test_create_trial_invalid_phase(in_memory_session: Session) -> None:
    """Test that invalid phase raises ValidationError."""
    input_data = CreateTrialInput(name="Invalid Trial", phase="Phase V")

    with pytest.raises(ValidationError, match="Invalid phase"):
        create_trial_handler(in_memory_session, input_data)

    # Verify no trial was created
    trials = in_memory_session.query(Trial).all()
    assert len(trials) == 0


def test_create_trial_audit_on_failure(in_memory_session: Session) -> None:
    """Test that audit log is created on failure."""
    input_data = CreateTrialInput(name="Fail Trial", phase="Invalid Phase")

    with pytest.raises(ValidationError):
        create_trial_handler(in_memory_session, input_data)

    # Verify error audit log was created
    audit_logs = in_memory_session.query(AuditLog).all()
    assert len(audit_logs) == 1
    assert audit_logs[0].action == "create_trial_failed"
    assert audit_logs[0].entity_id == "error"
    assert "ValidationError" in audit_logs[0].payload_json


def test_create_trial_multiple(in_memory_session: Session) -> None:
    """Test creating multiple trials."""
    input1 = CreateTrialInput(name="Trial 1", phase="Phase I")
    input2 = CreateTrialInput(name="Trial 2", phase="Phase II")

    result1 = create_trial_handler(in_memory_session, input1)
    result2 = create_trial_handler(in_memory_session, input2)

    assert result1.id != result2.id
    assert result1.name == "Trial 1"
    assert result2.name == "Trial 2"

    # Verify both in database
    trials = in_memory_session.query(Trial).all()
    assert len(trials) == 2
