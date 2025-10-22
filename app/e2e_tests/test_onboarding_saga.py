"""
E2E tests for trial onboarding saga/workflow.

Tests the multi-step workflow orchestration and error recovery.
"""


def test_onboarding_saga_happy_path(graphql_client):
    """Test successful trial onboarding workflow."""
    # Start onboarding workflow
    start_mutation = """
        mutation StartOnboarding($input: OnboardTrialInput!) {
            startOnboarding(input: $input) {
                sagaId
                trialId
                state
                message
            }
        }
    """

    onboarding_input = {
        "input": {
            "name": "Onboarded Trial",
            "phase": "Phase II",
            "initialProtocolVersion": "v1.0",
            "sites": [
                {"name": "Site Alpha", "country": "USA"},
                {"name": "Site Beta", "country": "Germany"}
            ]
        }
    }

    start_result = graphql_client(start_mutation, onboarding_input)
    assert "errors" not in start_result, f"GraphQL errors: {start_result.get('errors')}"

    saga_data = start_result["data"]["startOnboarding"]
    assert saga_data["state"] == "COMPLETED"
    assert saga_data["sagaId"] is not None
    assert saga_data["trialId"] is not None
    assert "Successfully" in saga_data["message"]

    saga_id = saga_data["sagaId"]
    trial_id = saga_data["trialId"]

    # Check onboarding status
    status_query = """
        query OnboardingStatus($sagaId: Int!) {
            onboardingStatus(sagaId: $sagaId) {
                sagaId
                trialId
                state
                error
                createdAt
                updatedAt
            }
        }
    """

    status_result = graphql_client(status_query, {"sagaId": saga_id})
    assert "errors" not in status_result, f"GraphQL errors: {status_result.get('errors')}"

    status_data = status_result["data"]["onboardingStatus"]
    assert status_data["sagaId"] == saga_id
    assert status_data["trialId"] == trial_id
    assert status_data["state"] == "COMPLETED"
    assert status_data["error"] is None

    # Verify trial was created with sites
    trial_query = """
        query GetTrial($id: Int!) {
            trialById(id: $id) {
                id
                name
                phase
                status
                sites {
                    name
                    country
                }
            }
        }
    """

    trial_result = graphql_client(trial_query, {"id": trial_id})
    assert "errors" not in trial_result, f"GraphQL errors: {trial_result.get('errors')}"

    trial_data = trial_result["data"]["trialById"]
    assert trial_data["name"] == "Onboarded Trial"
    assert trial_data["phase"] == "Phase II"
    assert trial_data["status"] == "draft"
    assert len(trial_data["sites"]) == 2

    site_names = {site["name"] for site in trial_data["sites"]}
    assert site_names == {"Site Alpha", "Site Beta"}

    # Verify audit logs were created
    audit_query = """
        query AuditLog($input: GetAuditLogInput!) {
            auditLog(input: $input) {
                entries {
                    action
                    entity
                    entityId
                }
            }
        }
    """

    audit_result = graphql_client(
        audit_query,
        {"input": {"entity": "saga", "entityId": str(saga_id), "limit": 10}}
    )
    assert "errors" not in audit_result, f"GraphQL errors: {audit_result.get('errors')}"

    audit_logs = audit_result["data"]["auditLog"]["entries"]
    assert len(audit_logs) > 0

    # Should have audit for start_onboarding
    actions = [log["action"] for log in audit_logs]
    assert "start_onboarding" in actions


def test_onboarding_saga_with_invalid_phase(graphql_client):
    """Test that saga handles errors gracefully."""
    start_mutation = """
        mutation StartOnboarding($input: OnboardTrialInput!) {
            startOnboarding(input: $input) {
                sagaId
                trialId
                state
                message
            }
        }
    """

    # Use invalid phase
    invalid_input = {
        "input": {
            "name": "Invalid Phase Trial",
            "phase": "Phase X",  # Invalid
            "initialProtocolVersion": "v1.0",
            "sites": [{"name": "Test Site", "country": "USA"}]
        }
    }

    result = graphql_client(start_mutation, invalid_input)
    assert "errors" not in result, f"GraphQL errors: {result.get('errors')}"

    saga_data = result["data"]["startOnboarding"]
    assert saga_data["state"] == "ERROR"
    assert saga_data["sagaId"] is not None
    assert "failed" in saga_data["message"].lower()

    # Verify saga status shows error
    status_query = """
        query OnboardingStatus($sagaId: Int!) {
            onboardingStatus(sagaId: $sagaId) {
                sagaId
                state
                error
            }
        }
    """

    status_result = graphql_client(
        status_query,
        {"sagaId": saga_data["sagaId"]}
    )

    status_data = status_result["data"]["onboardingStatus"]
    assert status_data["state"] == "ERROR"
    assert status_data["error"] is not None
    assert "Invalid phase" in status_data["error"]


def test_onboarding_with_no_sites(graphql_client):
    """Test that onboarding works with no sites."""
    start_mutation = """
        mutation StartOnboarding($input: OnboardTrialInput!) {
            startOnboarding(input: $input) {
                sagaId
                trialId
                state
                message
            }
        }
    """

    input_no_sites = {
        "input": {
            "name": "Trial Without Sites",
            "phase": "Phase I",
            "initialProtocolVersion": "v2.0",
            "sites": []
        }
    }

    result = graphql_client(start_mutation, input_no_sites)
    assert "errors" not in result, f"GraphQL errors: {result.get('errors')}"

    saga_data = result["data"]["startOnboarding"]
    assert saga_data["state"] == "COMPLETED"
    assert saga_data["trialId"] is not None

    # Verify trial exists with no sites
    trial_query = """
        query GetTrial($id: Int!) {
            trialById(id: $id) {
                name
                sites {
                    id
                }
            }
        }
    """

    trial_result = graphql_client(
        trial_query,
        {"id": saga_data["trialId"]}
    )

    trial_data = trial_result["data"]["trialById"]
    assert trial_data["name"] == "Trial Without Sites"
    assert len(trial_data["sites"]) == 0


def test_query_nonexistent_saga_status(graphql_client):
    """Test that querying non-existent saga returns error."""
    status_query = """
        query OnboardingStatus($sagaId: Int!) {
            onboardingStatus(sagaId: $sagaId) {
                sagaId
                state
            }
        }
    """

    result = graphql_client(status_query, {"sagaId": 99999})

    # Should have error
    assert "errors" in result
    error_message = result["errors"][0]["message"]
    assert "not found" in error_message.lower()
