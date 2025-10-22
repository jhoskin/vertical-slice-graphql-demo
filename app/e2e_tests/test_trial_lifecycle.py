"""
E2E tests for trial lifecycle: Create → Get → Update.

Tests the complete flow of creating a trial, retrieving it, and updating its metadata.
"""


def test_create_get_update_trial_lifecycle(graphql_client):
    """Test complete trial lifecycle from creation to update."""
    # Step 1: Create a trial
    create_mutation = """
        mutation CreateTrial($input: CreateTrialInput!) {
            createTrial(input: $input) {
                id
                name
                phase
                status
            }
        }
    """

    create_variables = {
        "input": {
            "name": "E2E Test Trial",
            "phase": "Phase I"
        }
    }

    create_result = graphql_client(create_mutation, create_variables)
    assert "errors" not in create_result, f"GraphQL errors: {create_result.get('errors')}"
    assert create_result["data"]["createTrial"]["name"] == "E2E Test Trial"
    assert create_result["data"]["createTrial"]["phase"] == "Phase I"
    assert create_result["data"]["createTrial"]["status"] == "draft"

    trial_id = create_result["data"]["createTrial"]["id"]

    # Step 2: Get the trial by ID
    get_query = """
        query GetTrial($id: Int!) {
            trialById(id: $id) {
                id
                name
                phase
                status
                createdAt
                sites {
                    id
                    name
                    country
                    linkStatus
                }
            }
        }
    """

    get_variables = {"id": trial_id}

    get_result = graphql_client(get_query, get_variables)
    assert "errors" not in get_result, f"GraphQL errors: {get_result.get('errors')}"
    assert get_result["data"]["trialById"]["id"] == trial_id
    assert get_result["data"]["trialById"]["name"] == "E2E Test Trial"
    assert get_result["data"]["trialById"]["phase"] == "Phase I"
    assert get_result["data"]["trialById"]["status"] == "draft"
    assert get_result["data"]["trialById"]["sites"] == []

    # Step 3: Update trial metadata
    update_mutation = """
        mutation UpdateTrial($input: UpdateTrialMetadataInput!) {
            updateTrialMetadata(input: $input) {
                id
                name
                phase
                status
                changes
            }
        }
    """

    update_variables = {
        "input": {
            "trialId": trial_id,
            "phase": "Phase II",
            "name": "Updated Trial Name"
        }
    }

    update_result = graphql_client(update_mutation, update_variables)
    assert "errors" not in update_result, f"GraphQL errors: {update_result.get('errors')}"
    assert update_result["data"]["updateTrialMetadata"]["id"] == trial_id
    assert update_result["data"]["updateTrialMetadata"]["phase"] == "Phase II"
    assert update_result["data"]["updateTrialMetadata"]["name"] == "Updated Trial Name"

    # Verify changes were tracked
    changes = update_result["data"]["updateTrialMetadata"]["changes"]
    assert "phase" in changes
    assert "name" in changes

    # Step 4: Verify updated data persists
    final_get_result = graphql_client(get_query, get_variables)
    assert "errors" not in final_get_result, f"GraphQL errors: {final_get_result.get('errors')}"
    assert final_get_result["data"]["trialById"]["phase"] == "Phase II"
    assert final_get_result["data"]["trialById"]["name"] == "Updated Trial Name"


def test_list_trials_pagination(graphql_client):
    """Test listing trials with pagination."""
    # Create multiple trials
    create_mutation = """
        mutation CreateTrial($input: CreateTrialInput!) {
            createTrial(input: $input) {
                id
                name
            }
        }
    """

    for i in range(5):
        variables = {
            "input": {
                "name": f"Trial {i}",
                "phase": "Phase I"
            }
        }
        graphql_client(create_mutation, variables)

    # List trials with pagination
    list_query = """
        query ListTrials($input: ListTrialsInput!) {
            listTrials(input: $input) {
                items {
                    id
                    name
                    phase
                    siteCount
                }
                total
            }
        }
    """

    # Get first page
    result1 = graphql_client(list_query, {"input": {"limit": 3, "offset": 0}})
    assert "errors" not in result1, f"GraphQL errors: {result1.get('errors')}"
    assert len(result1["data"]["listTrials"]["items"]) == 3
    assert result1["data"]["listTrials"]["total"] == 5

    # Get second page
    result2 = graphql_client(list_query, {"input": {"limit": 3, "offset": 3}})
    assert "errors" not in result2, f"GraphQL errors: {result2.get('errors')}"
    assert len(result2["data"]["listTrials"]["items"]) == 2
    assert result2["data"]["listTrials"]["total"] == 5


def test_invalid_phase_transition(graphql_client):
    """Test that invalid phase transitions are rejected."""
    # Create a trial
    create_mutation = """
        mutation CreateTrial($input: CreateTrialInput!) {
            createTrial(input: $input) {
                id
                phase
            }
        }
    """

    create_result = graphql_client(
        create_mutation,
        {"input": {"name": "Test Trial", "phase": "Phase III"}}
    )
    trial_id = create_result["data"]["createTrial"]["id"]

    # Try to update with invalid phase
    update_mutation = """
        mutation UpdateTrial($input: UpdateTrialMetadataInput!) {
            updateTrialMetadata(input: $input) {
                id
                phase
            }
        }
    """

    update_result = graphql_client(
        update_mutation,
        {"input": {"trialId": trial_id, "phase": "Phase I"}}
    )

    # Should have error about invalid transition
    assert "errors" in update_result
    error_message = update_result["errors"][0]["message"]
    assert "Cannot transition" in error_message or "Invalid" in error_message
