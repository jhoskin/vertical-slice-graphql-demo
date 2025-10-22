"""
Unit tests for database models.
"""
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.database.models import (
    AuditLog,
    Base,
    ProtocolVersion,
    Site,
    Trial,
    TrialSite,
    SagaOnboardTrial,
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


def test_trial_creation(in_memory_session: Session) -> None:
    """Test creating a trial."""
    trial = Trial(name="Test Trial", phase="Phase I", status="draft")
    in_memory_session.add(trial)
    in_memory_session.commit()

    assert trial.id is not None
    assert trial.name == "Test Trial"
    assert trial.phase == "Phase I"
    assert trial.status == "draft"
    assert isinstance(trial.created_at, datetime)


def test_site_creation(in_memory_session: Session) -> None:
    """Test creating a site."""
    site = Site(name="Memorial Hospital", country="USA")
    in_memory_session.add(site)
    in_memory_session.commit()

    assert site.id is not None
    assert site.name == "Memorial Hospital"
    assert site.country == "USA"


def test_trial_site_link(in_memory_session: Session) -> None:
    """Test linking a site to a trial."""
    trial = Trial(name="Test Trial", phase="Phase I", status="draft")
    site = Site(name="Memorial Hospital", country="USA")
    in_memory_session.add_all([trial, site])
    in_memory_session.flush()

    trial_site = TrialSite(trial_id=trial.id, site_id=site.id, status="pending")
    in_memory_session.add(trial_site)
    in_memory_session.commit()

    assert trial_site.trial_id == trial.id
    assert trial_site.site_id == site.id
    assert trial_site.status == "pending"


def test_trial_site_unique_constraint(in_memory_session: Session) -> None:
    """Test that trial-site link enforces uniqueness."""
    trial = Trial(name="Test Trial", phase="Phase I", status="draft")
    site = Site(name="Memorial Hospital", country="USA")
    in_memory_session.add_all([trial, site])
    in_memory_session.flush()

    # Add first link
    trial_site1 = TrialSite(trial_id=trial.id, site_id=site.id, status="pending")
    in_memory_session.add(trial_site1)
    in_memory_session.commit()

    # Try to add duplicate link
    trial_site2 = TrialSite(trial_id=trial.id, site_id=site.id, status="active")
    in_memory_session.add(trial_site2)

    with pytest.raises(Exception):  # SQLAlchemy will raise IntegrityError
        in_memory_session.commit()


def test_protocol_version_creation(in_memory_session: Session) -> None:
    """Test creating a protocol version."""
    trial = Trial(name="Test Trial", phase="Phase I", status="draft")
    in_memory_session.add(trial)
    in_memory_session.flush()

    protocol = ProtocolVersion(
        trial_id=trial.id, version="v1.0", notes="Initial protocol"
    )
    in_memory_session.add(protocol)
    in_memory_session.commit()

    assert protocol.id is not None
    assert protocol.trial_id == trial.id
    assert protocol.version == "v1.0"
    assert protocol.notes == "Initial protocol"


def test_audit_log_creation(in_memory_session: Session) -> None:
    """Test creating an audit log entry."""
    audit = AuditLog(
        user="test_user",
        action="create_trial",
        entity="trial",
        entity_id="123",
        payload_json='{"name": "Test"}',
    )
    in_memory_session.add(audit)
    in_memory_session.commit()

    assert audit.id is not None
    assert audit.user == "test_user"
    assert audit.action == "create_trial"
    assert audit.entity == "trial"
    assert audit.entity_id == "123"


def test_saga_onboard_trial_creation(in_memory_session: Session) -> None:
    """Test creating a saga state entry."""
    saga = SagaOnboardTrial(state="STARTED", trial_id=None, error=None)
    in_memory_session.add(saga)
    in_memory_session.commit()

    assert saga.id is not None
    assert saga.state == "STARTED"
    assert saga.trial_id is None
    assert saga.error is None
    assert isinstance(saga.created_at, datetime)
    assert isinstance(saga.updated_at, datetime)


def test_trial_relationships(in_memory_session: Session) -> None:
    """Test trial relationships with sites and protocols."""
    trial = Trial(name="Test Trial", phase="Phase I", status="draft")
    site = Site(name="Memorial Hospital", country="USA")
    in_memory_session.add_all([trial, site])
    in_memory_session.flush()

    trial_site = TrialSite(trial_id=trial.id, site_id=site.id, status="active")
    protocol = ProtocolVersion(trial_id=trial.id, version="v1.0", notes="Initial")
    in_memory_session.add_all([trial_site, protocol])
    in_memory_session.commit()

    # Refresh to load relationships
    in_memory_session.refresh(trial)

    assert len(trial.trial_sites) == 1
    assert len(trial.protocol_versions) == 1
    assert trial.trial_sites[0].site.name == "Memorial Hospital"
    assert trial.protocol_versions[0].version == "v1.0"
