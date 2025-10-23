"""
E2E tests for synchronous saga workflow.
"""
from app.infrastructure.database.models import ProtocolVersion, Trial, TrialSite


def test_sync_saga_success(test_client, graphql_client):
    """Test successful synchronous saga execution via GraphQL."""
    mutation = """
        mutation OnboardTrialSync($input: OnboardTrialSyncInput!) {
            onboardTrialSync(input: $input) {
                success
                trialId
                message
                stepsCompleted
            }
        }
    """

    variables = {
        "input": {
            "name": "E2E Test Trial",
            "phase": "Phase I",
            "initialProtocolVersion": "v1.0",
            "sites": [
                {"name": "Site A", "country": "USA"},
                {"name": "Site B", "country": "UK"},
            ],
        }
    }

    result = graphql_client(mutation, variables)

    assert "errors" not in result

    data = result["data"]["onboardTrialSync"]

    # Verify response
    assert data["success"] is True
    assert data["trialId"] is not None
    assert "Successfully onboarded" in data["message"]
    assert "create_trial" in data["stepsCompleted"]
    assert "add_protocol" in data["stepsCompleted"]
    assert "register_site_1" in data["stepsCompleted"]
    assert "register_site_2" in data["stepsCompleted"]

    trial_id = data["trialId"]

    # Verify database state
    from app.infrastructure.database import session as session_module
    session = session_module.SessionLocal()
    try:
        # Check trial exists
        trial = session.query(Trial).filter_by(id=trial_id).first()
        assert trial is not None
        assert trial.name == "E2E Test Trial"
        assert trial.phase == "Phase I"

        # Check protocol exists
        protocol = session.query(ProtocolVersion).filter_by(trial_id=trial_id).first()
        assert protocol is not None
        assert protocol.version == "v1.0"

        # Check sites exist
        links = session.query(TrialSite).filter_by(trial_id=trial_id).all()
        assert len(links) == 2

    finally:
        session.close()


def test_sync_saga_failure_with_compensation(test_client, graphql_client):
    """Test saga failure triggers compensation via GraphQL."""
    mutation = """
        mutation OnboardTrialSync($input: OnboardTrialSyncInput!) {
            onboardTrialSync(input: $input) {
                success
                trialId
                message
                stepsCompleted
            }
        }
    """

    variables = {
        "input": {
            "name": "Invalid Trial",
            "phase": "Phase X",  # Invalid phase
            "initialProtocolVersion": "v1.0",
            "sites": [{"name": "Site A", "country": "USA"}],
        }
    }

    result = graphql_client(mutation, variables)

    # Should have GraphQL errors
    assert "errors" in result

    # Verify database state - should be clean (compensated)
    from app.infrastructure.database import session as session_module
    session = session_module.SessionLocal()
    try:
        # No trials should exist (compensation should have cleaned up)
        trials = session.query(Trial).all()
        assert len(trials) == 0

        # No protocols should exist
        protocols = session.query(ProtocolVersion).all()
        assert len(protocols) == 0

        # No site links should exist
        links = session.query(TrialSite).all()
        assert len(links) == 0

    finally:
        session.close()


def test_sync_saga_no_sites(test_client, graphql_client):
    """Test saga with no sites to register."""
    mutation = """
        mutation OnboardTrialSync($input: OnboardTrialSyncInput!) {
            onboardTrialSync(input: $input) {
                success
                trialId
                message
                stepsCompleted
            }
        }
    """

    variables = {
        "input": {
            "name": "Trial Without Sites",
            "phase": "Phase II",
            "initialProtocolVersion": "v2.0",
            "sites": [],
        }
    }

    result = graphql_client(mutation, variables)

    assert "errors" not in result

    data = result["data"]["onboardTrialSync"]

    # Verify response
    assert data["success"] is True
    assert data["trialId"] is not None
    assert "create_trial" in data["stepsCompleted"]
    assert "add_protocol" in data["stepsCompleted"]
    # No site registration steps
    assert len([s for s in data["stepsCompleted"] if "register_site" in s]) == 0

    trial_id = data["trialId"]

    # Verify database state
    from app.infrastructure.database import session as session_module
    session = session_module.SessionLocal()
    try:
        # Check trial and protocol exist
        trial = session.query(Trial).filter_by(id=trial_id).first()
        assert trial is not None

        protocol = session.query(ProtocolVersion).filter_by(trial_id=trial_id).first()
        assert protocol is not None

        # No site links
        links = session.query(TrialSite).filter_by(trial_id=trial_id).all()
        assert len(links) == 0

    finally:
        session.close()


def test_sync_saga_multiple_workflows(test_client, graphql_client):
    """Test running multiple saga workflows sequentially."""
    mutation = """
        mutation OnboardTrialSync($input: OnboardTrialSyncInput!) {
            onboardTrialSync(input: $input) {
                success
                trialId
                message
                stepsCompleted
            }
        }
    """

    # First workflow
    variables1 = {
        "input": {
            "name": "Trial 1",
            "phase": "Phase I",
            "initialProtocolVersion": "v1.0",
            "sites": [{"name": "Site A", "country": "USA"}],
        }
    }

    result1 = graphql_client(mutation, variables1)
    assert "errors" not in result1
    data1 = result1["data"]["onboardTrialSync"]
    assert data1["success"] is True
    trial_id_1 = data1["trialId"]

    # Second workflow
    variables2 = {
        "input": {
            "name": "Trial 2",
            "phase": "Phase II",
            "initialProtocolVersion": "v1.0",
            "sites": [{"name": "Site B", "country": "UK"}],
        }
    }

    result2 = graphql_client(mutation, variables2)
    assert "errors" not in result2
    data2 = result2["data"]["onboardTrialSync"]
    assert data2["success"] is True
    trial_id_2 = data2["trialId"]

    # Verify both trials exist
    assert trial_id_1 != trial_id_2

    from app.infrastructure.database import session as session_module
    session = session_module.SessionLocal()
    try:
        trials = session.query(Trial).all()
        assert len(trials) == 2

    finally:
        session.close()
