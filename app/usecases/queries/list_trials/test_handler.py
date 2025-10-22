"""
Unit tests for list_trials handler.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.database.models import Base, Site, Trial, TrialSite
from app.usecases.queries.list_trials.handler import list_trials_handler
from app.usecases.queries.list_trials.types import ListTrialsInput


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
def sample_trials(in_memory_session: Session) -> list[Trial]:
    """Create sample trials for testing."""
    trials = [
        Trial(name="Alpha Trial", phase="Phase I", status="active"),
        Trial(name="Beta Trial", phase="Phase II", status="active"),
        Trial(name="Gamma Trial", phase="Phase III", status="draft"),
        Trial(name="Delta Trial", phase="Phase I", status="completed"),
        Trial(name="Epsilon Trial", phase="Phase II", status="paused"),
    ]
    in_memory_session.add_all(trials)
    in_memory_session.flush()

    # Add sites to some trials
    site1 = Site(name="Site A", country="USA")
    site2 = Site(name="Site B", country="UK")
    in_memory_session.add_all([site1, site2])
    in_memory_session.flush()

    # Link sites to first trial
    link1 = TrialSite(trial_id=trials[0].id, site_id=site1.id, status="active")
    link2 = TrialSite(trial_id=trials[0].id, site_id=site2.id, status="active")
    in_memory_session.add_all([link1, link2])

    # Link one site to second trial
    link3 = TrialSite(trial_id=trials[1].id, site_id=site1.id, status="pending")
    in_memory_session.add(link3)

    in_memory_session.commit()
    return trials


def test_list_trials_no_filters(
    in_memory_session: Session, sample_trials: list[Trial]
) -> None:
    """Test listing all trials without filters."""
    input_data = ListTrialsInput()
    result = list_trials_handler(in_memory_session, input_data)

    assert result.total == 5
    assert len(result.items) == 5

    # Should be ordered by created_at desc (most recent first)
    trial_names = [item.name for item in result.items]
    assert "Epsilon Trial" in trial_names


def test_list_trials_filter_by_phase(
    in_memory_session: Session, sample_trials: list[Trial]
) -> None:
    """Test filtering by phase."""
    input_data = ListTrialsInput(phase="Phase I")
    result = list_trials_handler(in_memory_session, input_data)

    assert result.total == 2
    assert len(result.items) == 2
    assert all(item.phase == "Phase I" for item in result.items)


def test_list_trials_filter_by_status(
    in_memory_session: Session, sample_trials: list[Trial]
) -> None:
    """Test filtering by status."""
    input_data = ListTrialsInput(status="active")
    result = list_trials_handler(in_memory_session, input_data)

    assert result.total == 2
    assert len(result.items) == 2
    assert all(item.status == "active" for item in result.items)


def test_list_trials_filter_by_phase_and_status(
    in_memory_session: Session, sample_trials: list[Trial]
) -> None:
    """Test filtering by multiple criteria."""
    input_data = ListTrialsInput(phase="Phase II", status="active")
    result = list_trials_handler(in_memory_session, input_data)

    assert result.total == 1
    assert len(result.items) == 1
    assert result.items[0].name == "Beta Trial"


def test_list_trials_search_by_name(
    in_memory_session: Session, sample_trials: list[Trial]
) -> None:
    """Test case-insensitive search in trial name."""
    # Search for "alpha" (case-insensitive)
    input_data = ListTrialsInput(search="alpha")
    result = list_trials_handler(in_memory_session, input_data)

    assert result.total == 1
    assert result.items[0].name == "Alpha Trial"

    # Search for "trial" (should match all)
    input_data = ListTrialsInput(search="trial")
    result = list_trials_handler(in_memory_session, input_data)
    assert result.total == 5


def test_list_trials_pagination(
    in_memory_session: Session, sample_trials: list[Trial]
) -> None:
    """Test pagination."""
    # Get first page (limit 2)
    input_data = ListTrialsInput(limit=2, offset=0)
    result = list_trials_handler(in_memory_session, input_data)

    assert result.total == 5  # Total count remains the same
    assert len(result.items) == 2

    # Get second page
    input_data = ListTrialsInput(limit=2, offset=2)
    result = list_trials_handler(in_memory_session, input_data)

    assert result.total == 5
    assert len(result.items) == 2

    # Get third page (only 1 item left)
    input_data = ListTrialsInput(limit=2, offset=4)
    result = list_trials_handler(in_memory_session, input_data)

    assert result.total == 5
    assert len(result.items) == 1


def test_list_trials_site_count(
    in_memory_session: Session, sample_trials: list[Trial]
) -> None:
    """Test that site counts are correctly calculated."""
    input_data = ListTrialsInput()
    result = list_trials_handler(in_memory_session, input_data)

    # Find Alpha Trial (has 2 sites)
    alpha = next(item for item in result.items if item.name == "Alpha Trial")
    assert alpha.site_count == 2

    # Find Beta Trial (has 1 site)
    beta = next(item for item in result.items if item.name == "Beta Trial")
    assert beta.site_count == 1

    # Find Gamma Trial (has 0 sites)
    gamma = next(item for item in result.items if item.name == "Gamma Trial")
    assert gamma.site_count == 0


def test_list_trials_empty_result(in_memory_session: Session) -> None:
    """Test listing with no matching trials."""
    input_data = ListTrialsInput(phase="Phase V")
    result = list_trials_handler(in_memory_session, input_data)

    assert result.total == 0
    assert len(result.items) == 0


def test_list_trials_combined_filters(
    in_memory_session: Session, sample_trials: list[Trial]
) -> None:
    """Test combining search with other filters."""
    # Search for "Beta" + filter by status "active"
    input_data = ListTrialsInput(search="beta", status="active")
    result = list_trials_handler(in_memory_session, input_data)

    assert result.total == 1
    assert result.items[0].name == "Beta Trial"
    assert result.items[0].status == "active"


def test_list_trials_ordering(
    in_memory_session: Session, sample_trials: list[Trial]
) -> None:
    """Test that trials are ordered by created_at descending."""
    input_data = ListTrialsInput()
    result = list_trials_handler(in_memory_session, input_data)

    # Newest should be first (Epsilon was added last)
    assert result.items[0].name == "Epsilon Trial"

    # Verify descending order
    for i in range(len(result.items) - 1):
        assert result.items[i].created_at >= result.items[i + 1].created_at
