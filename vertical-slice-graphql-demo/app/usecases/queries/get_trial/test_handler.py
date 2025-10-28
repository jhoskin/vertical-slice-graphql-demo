"""
Unit tests for get_trial handler.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.database.models import (
    Base,
    ProtocolVersion,
    Site,
    Trial,
    TrialSite,
)
from app.usecases.queries.get_trial.handler import (
    TrialNotFoundError,
    get_trial_handler,
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
def trial_with_sites_and_protocol(in_memory_session: Session) -> Trial:
    """Create a trial with sites and protocol for testing."""
    # Create trial
    trial = Trial(name="Test Trial", phase="Phase I", status="active")
    in_memory_session.add(trial)
    in_memory_session.flush()

    # Create sites
    site1 = Site(name="Site A", country="USA")
    site2 = Site(name="Site B", country="UK")
    in_memory_session.add_all([site1, site2])
    in_memory_session.flush()

    # Link sites to trial
    link1 = TrialSite(trial_id=trial.id, site_id=site1.id, status="active")
    link2 = TrialSite(trial_id=trial.id, site_id=site2.id, status="pending")
    in_memory_session.add_all([link1, link2])

    # Create protocol versions
    protocol1 = ProtocolVersion(
        trial_id=trial.id, version="v1.0", notes="Initial protocol"
    )
    protocol2 = ProtocolVersion(
        trial_id=trial.id, version="v1.1", notes="Updated protocol"
    )
    in_memory_session.add_all([protocol1, protocol2])
    in_memory_session.commit()

    return trial


def test_get_trial_success(
    in_memory_session: Session, trial_with_sites_and_protocol: Trial
) -> None:
    """Test successful trial retrieval."""
    result = get_trial_handler(in_memory_session, trial_with_sites_and_protocol.id)

    # Verify trial details
    assert result.id == trial_with_sites_and_protocol.id
    assert result.name == "Test Trial"
    assert result.phase == "Phase I"
    assert result.status == "active"
    assert result.created_at is not None

    # Verify sites
    assert len(result.sites) == 2
    site_names = {site.name for site in result.sites}
    assert site_names == {"Site A", "Site B"}

    # Verify link statuses
    site_a = next(s for s in result.sites if s.name == "Site A")
    site_b = next(s for s in result.sites if s.name == "Site B")
    assert site_a.link_status == "active"
    assert site_b.link_status == "pending"

    # Verify latest protocol (should be v1.1)
    assert result.latest_protocol is not None
    assert result.latest_protocol.version == "v1.1"
    assert result.latest_protocol.notes == "Updated protocol"


def test_get_trial_not_found(in_memory_session: Session) -> None:
    """Test that querying non-existent trial raises error."""
    with pytest.raises(TrialNotFoundError, match="Trial with id 999 not found"):
        get_trial_handler(in_memory_session, 999)


def test_get_trial_no_sites(in_memory_session: Session) -> None:
    """Test trial with no sites."""
    trial = Trial(name="Trial No Sites", phase="Phase II", status="draft")
    in_memory_session.add(trial)
    in_memory_session.commit()

    result = get_trial_handler(in_memory_session, trial.id)

    assert result.id == trial.id
    assert result.name == "Trial No Sites"
    assert len(result.sites) == 0
    assert result.latest_protocol is None


def test_get_trial_no_protocol(in_memory_session: Session) -> None:
    """Test trial with sites but no protocol."""
    trial = Trial(name="Trial No Protocol", phase="Phase III", status="active")
    site = Site(name="Site X", country="USA")
    in_memory_session.add_all([trial, site])
    in_memory_session.flush()

    link = TrialSite(trial_id=trial.id, site_id=site.id, status="active")
    in_memory_session.add(link)
    in_memory_session.commit()

    result = get_trial_handler(in_memory_session, trial.id)

    assert result.id == trial.id
    assert len(result.sites) == 1
    assert result.sites[0].name == "Site X"
    assert result.latest_protocol is None


def test_get_trial_latest_protocol_ordering(in_memory_session: Session) -> None:
    """Test that latest protocol is correctly selected by created_at."""
    trial = Trial(name="Protocol Test", phase="Phase I", status="draft")
    in_memory_session.add(trial)
    in_memory_session.flush()

    # Add protocols in specific order
    old_protocol = ProtocolVersion(
        trial_id=trial.id, version="v1.0", notes="Old"
    )
    in_memory_session.add(old_protocol)
    in_memory_session.flush()

    # Newer protocol (created later)
    new_protocol = ProtocolVersion(
        trial_id=trial.id, version="v2.0", notes="New"
    )
    in_memory_session.add(new_protocol)
    in_memory_session.commit()

    result = get_trial_handler(in_memory_session, trial.id)

    # Should return the newer protocol
    assert result.latest_protocol is not None
    assert result.latest_protocol.version == "v2.0"
    assert result.latest_protocol.notes == "New"


def test_get_trial_eager_loading(
    in_memory_session: Session, trial_with_sites_and_protocol: Trial
) -> None:
    """Test that eager loading works (no additional queries after initial load)."""
    # Get trial
    result = get_trial_handler(in_memory_session, trial_with_sites_and_protocol.id)

    # Close session to ensure no lazy loading happens
    in_memory_session.close()

    # Should still be able to access all loaded data
    assert result.name == "Test Trial"
    assert len(result.sites) == 2
    assert result.sites[0].name in ["Site A", "Site B"]
    assert result.latest_protocol is not None
    assert result.latest_protocol.version == "v1.1"
