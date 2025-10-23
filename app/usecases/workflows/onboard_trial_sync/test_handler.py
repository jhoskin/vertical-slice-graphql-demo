"""
Unit tests for synchronous onboard trial saga handler.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.database.models import Base, ProtocolVersion, Trial, TrialSite
from app.usecases.workflows.onboard_trial_sync.handler import (
    SagaFailedError,
    onboard_trial_sync_handler,
)
from app.usecases.workflows.onboard_trial_sync.types import (
    OnboardTrialSyncInput,
    SiteInput,
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


def test_saga_success_all_steps(in_memory_session: Session) -> None:
    """Test successful saga execution with all steps completing."""
    input_data = OnboardTrialSyncInput(
        name="Test Trial",
        phase="Phase I",
        initial_protocol_version="v1.0",
        sites=[
            SiteInput(name="Site A", country="USA"),
            SiteInput(name="Site B", country="UK"),
        ],
    )

    result = onboard_trial_sync_handler(in_memory_session, input_data)

    assert result.success is True
    assert result.trial_id is not None
    assert "Successfully onboarded" in result.message
    assert "create_trial" in result.steps_completed
    assert "add_protocol" in result.steps_completed
    assert "register_site_1" in result.steps_completed
    assert "register_site_2" in result.steps_completed

    # Verify trial was created
    trial = in_memory_session.query(Trial).filter_by(id=result.trial_id).first()
    assert trial is not None
    assert trial.name == "Test Trial"

    # Verify protocol was added
    protocol = (
        in_memory_session.query(ProtocolVersion).filter_by(trial_id=result.trial_id).first()
    )
    assert protocol is not None
    assert protocol.version == "v1.0"

    # Verify sites were registered
    links = in_memory_session.query(TrialSite).filter_by(trial_id=result.trial_id).all()
    assert len(links) == 2


def test_saga_compensation_on_invalid_phase(in_memory_session: Session) -> None:
    """Test that saga compensates when trial creation fails due to invalid phase."""
    input_data = OnboardTrialSyncInput(
        name="Invalid Trial",
        phase="Phase X",  # Invalid phase
        initial_protocol_version="v1.0",
        sites=[SiteInput(name="Site A", country="USA")],
    )

    with pytest.raises(SagaFailedError):
        onboard_trial_sync_handler(in_memory_session, input_data)

    # Verify no trial was left in database
    trials = in_memory_session.query(Trial).all()
    assert len(trials) == 0


def test_saga_no_sites(in_memory_session: Session) -> None:
    """Test saga with no sites to register."""
    input_data = OnboardTrialSyncInput(
        name="Trial Without Sites",
        phase="Phase II",
        initial_protocol_version="v2.0",
        sites=[],
    )

    result = onboard_trial_sync_handler(in_memory_session, input_data)

    assert result.success is True
    assert result.trial_id is not None
    assert "create_trial" in result.steps_completed
    assert "add_protocol" in result.steps_completed
    # No site registration steps
    assert len([s for s in result.steps_completed if "register_site" in s]) == 0
