"""
Unit tests for update_trial_metadata handler.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.database.models import AuditLog, Base, Trial
from app.usecases.commands.trial_management._validation import ValidationError
from app.usecases.commands.trial_management.update_trial_metadata.handler import (
    TrialNotFoundError,
    update_trial_metadata_handler,
)
from app.usecases.commands.trial_management.update_trial_metadata.types import (
    UpdateTrialMetadataInput,
)


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
def sample_trial(in_memory_session: Session) -> Trial:
    """Create a sample trial for testing."""
    trial = Trial(name="Original Trial", phase="Phase I", status="draft")
    in_memory_session.add(trial)
    in_memory_session.flush()
    return trial


def test_update_trial_name(in_memory_session: Session, sample_trial: Trial) -> None:
    """Test updating trial name."""
    input_data = UpdateTrialMetadataInput(
        trial_id=sample_trial.id, name="Updated Trial"
    )

    result = update_trial_metadata_handler(in_memory_session, input_data)

    assert result.id == sample_trial.id
    assert result.name == "Updated Trial"
    assert result.phase == "Phase I"  # Unchanged
    assert "name: 'Original Trial' -> 'Updated Trial'" in result.changes

    # Verify audit log
    audit_logs = in_memory_session.query(AuditLog).all()
    assert len(audit_logs) == 1
    assert audit_logs[0].action == "update_trial_metadata"


def test_update_trial_phase(in_memory_session: Session, sample_trial: Trial) -> None:
    """Test updating trial phase with valid transition."""
    input_data = UpdateTrialMetadataInput(trial_id=sample_trial.id, phase="Phase II")

    result = update_trial_metadata_handler(in_memory_session, input_data)

    assert result.phase == "Phase II"
    assert result.name == "Original Trial"  # Unchanged
    assert "phase: 'Phase I' -> 'Phase II'" in result.changes


def test_update_trial_name_and_phase(
    in_memory_session: Session, sample_trial: Trial
) -> None:
    """Test updating both name and phase."""
    input_data = UpdateTrialMetadataInput(
        trial_id=sample_trial.id, name="New Name", phase="Phase II"
    )

    result = update_trial_metadata_handler(in_memory_session, input_data)

    assert result.name == "New Name"
    assert result.phase == "Phase II"
    assert "name:" in result.changes
    assert "phase:" in result.changes


def test_update_trial_no_changes(
    in_memory_session: Session, sample_trial: Trial
) -> None:
    """Test update with no actual changes."""
    input_data = UpdateTrialMetadataInput(
        trial_id=sample_trial.id, name="Original Trial", phase="Phase I"
    )

    result = update_trial_metadata_handler(in_memory_session, input_data)

    assert result.changes == "no changes"


def test_update_trial_invalid_phase_transition(
    in_memory_session: Session, sample_trial: Trial
) -> None:
    """Test that invalid phase transition raises ValidationError."""
    # Try to go from Phase I to Phase III (skipping Phase II)
    input_data = UpdateTrialMetadataInput(trial_id=sample_trial.id, phase="Phase III")

    with pytest.raises(ValidationError, match="Invalid phase transition"):
        update_trial_metadata_handler(in_memory_session, input_data)


def test_update_trial_invalid_phase(
    in_memory_session: Session, sample_trial: Trial
) -> None:
    """Test that invalid phase raises ValidationError."""
    input_data = UpdateTrialMetadataInput(trial_id=sample_trial.id, phase="Phase V")

    with pytest.raises(ValidationError, match="Invalid phase"):
        update_trial_metadata_handler(in_memory_session, input_data)


def test_update_trial_not_found(in_memory_session: Session) -> None:
    """Test that updating non-existent trial raises TrialNotFoundError."""
    input_data = UpdateTrialMetadataInput(trial_id=999, name="Not Found")

    with pytest.raises(TrialNotFoundError, match="Trial with id 999 not found"):
        update_trial_metadata_handler(in_memory_session, input_data)


def test_update_trial_partial_update(
    in_memory_session: Session, sample_trial: Trial
) -> None:
    """Test updating only name (phase is None)."""
    input_data = UpdateTrialMetadataInput(trial_id=sample_trial.id, name="Only Name")

    result = update_trial_metadata_handler(in_memory_session, input_data)

    assert result.name == "Only Name"
    assert result.phase == "Phase I"  # Unchanged
    assert "phase" not in result.changes  # Only name changed


def test_update_trial_audit_on_failure(
    in_memory_session: Session, sample_trial: Trial
) -> None:
    """Test that audit log is created on failure."""
    input_data = UpdateTrialMetadataInput(trial_id=sample_trial.id, phase="Invalid")

    with pytest.raises(ValidationError):
        update_trial_metadata_handler(in_memory_session, input_data)

    # Verify error audit log
    audit_logs = in_memory_session.query(AuditLog).all()
    assert len(audit_logs) == 1
    assert audit_logs[0].action == "update_trial_metadata_failed"
