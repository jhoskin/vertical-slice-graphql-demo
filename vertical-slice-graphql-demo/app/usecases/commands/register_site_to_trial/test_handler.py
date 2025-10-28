"""
Unit tests for register_site_to_trial handler.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.database.models import AuditLog, Base, Site, Trial, TrialSite
from app.usecases.commands.register_site_to_trial.handler import (
    DuplicateSiteLinkError,
    TrialNotFoundError,
    register_site_to_trial_handler,
)
from app.usecases.commands.register_site_to_trial.types import RegisterSiteToTrialInput


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
    trial = Trial(name="Test Trial", phase="Phase I", status="draft")
    in_memory_session.add(trial)
    in_memory_session.flush()
    return trial


def test_register_new_site_to_trial(
    in_memory_session: Session, sample_trial: Trial
) -> None:
    """Test registering a new site to a trial."""
    input_data = RegisterSiteToTrialInput(
        trial_id=sample_trial.id, site_name="Memorial Hospital", country="USA"
    )

    result = register_site_to_trial_handler(in_memory_session, input_data)

    # Verify result
    assert result.trial_id == sample_trial.id
    assert result.site_id is not None
    assert result.site_name == "Memorial Hospital"
    assert result.country == "USA"
    assert result.link_status == "pending"

    # Verify site was created
    site = in_memory_session.query(Site).filter_by(id=result.site_id).first()
    assert site is not None
    assert site.name == "Memorial Hospital"

    # Verify link was created
    link = (
        in_memory_session.query(TrialSite)
        .filter_by(trial_id=sample_trial.id, site_id=result.site_id)
        .first()
    )
    assert link is not None
    assert link.status == "pending"

    # Verify audit log
    audit_logs = in_memory_session.query(AuditLog).all()
    assert len(audit_logs) == 1
    assert audit_logs[0].action == "register_site_to_trial"


def test_register_existing_site_to_trial(
    in_memory_session: Session, sample_trial: Trial
) -> None:
    """Test registering an existing site to a trial (upsert behavior)."""
    # Create existing site
    existing_site = Site(name="Existing Hospital", country="UK")
    in_memory_session.add(existing_site)
    in_memory_session.flush()

    input_data = RegisterSiteToTrialInput(
        trial_id=sample_trial.id, site_name="Existing Hospital", country="UK"
    )

    result = register_site_to_trial_handler(in_memory_session, input_data)

    # Verify it used the existing site
    assert result.site_id == existing_site.id

    # Verify no duplicate site was created
    sites = in_memory_session.query(Site).filter_by(name="Existing Hospital").all()
    assert len(sites) == 1


def test_register_site_trial_not_found(in_memory_session: Session) -> None:
    """Test that registering to non-existent trial raises error."""
    input_data = RegisterSiteToTrialInput(
        trial_id=999, site_name="Some Hospital", country="USA"
    )

    with pytest.raises(TrialNotFoundError, match="Trial with id 999 not found"):
        register_site_to_trial_handler(in_memory_session, input_data)

    # Verify no site or link was created
    assert in_memory_session.query(Site).count() == 0
    assert in_memory_session.query(TrialSite).count() == 0


def test_register_duplicate_site_link(
    in_memory_session: Session, sample_trial: Trial
) -> None:
    """Test that duplicate site-trial link raises error."""
    # Register site once
    input_data = RegisterSiteToTrialInput(
        trial_id=sample_trial.id, site_name="Hospital", country="USA"
    )
    first_result = register_site_to_trial_handler(in_memory_session, input_data)
    in_memory_session.commit()

    # Try to register same site again
    with pytest.raises(DuplicateSiteLinkError):
        register_site_to_trial_handler(in_memory_session, input_data)


def test_register_site_atomic_transaction(
    in_memory_session: Session, sample_trial: Trial
) -> None:
    """Test that operation is atomic - both site and link created or neither."""
    # This is implicitly tested by other tests, but let's be explicit
    input_data = RegisterSiteToTrialInput(
        trial_id=sample_trial.id, site_name="Atomic Hospital", country="USA"
    )

    # Count before
    site_count_before = in_memory_session.query(Site).count()
    link_count_before = in_memory_session.query(TrialSite).count()

    result = register_site_to_trial_handler(in_memory_session, input_data)

    # Verify both site and link were created
    assert in_memory_session.query(Site).count() == site_count_before + 1
    assert in_memory_session.query(TrialSite).count() == link_count_before + 1


def test_register_site_rollback_on_failure(
    in_memory_session: Session, sample_trial: Trial
) -> None:
    """Test that transaction rolls back on failure."""
    # Create a site
    site = Site(name="Test Site", country="USA")
    in_memory_session.add(site)
    in_memory_session.flush()

    # Create initial link
    link = TrialSite(trial_id=sample_trial.id, site_id=site.id, status="active")
    in_memory_session.add(link)
    in_memory_session.commit()

    # Try to create duplicate link
    input_data = RegisterSiteToTrialInput(
        trial_id=sample_trial.id, site_name="Test Site", country="USA"
    )

    with pytest.raises(DuplicateSiteLinkError):
        register_site_to_trial_handler(in_memory_session, input_data)

    # Rollback the session
    in_memory_session.rollback()

    # Verify only one link exists (the original)
    links = in_memory_session.query(TrialSite).all()
    assert len(links) == 1
