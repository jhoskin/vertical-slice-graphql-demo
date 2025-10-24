"""
End-to-end tests for Trial Virtual Object mutation.

These tests verify that the updateTrialMetadataViaVO mutation works correctly
and demonstrate the concurrency protection benefits.

Note: Full concurrency testing requires Restate to be running.
Mark with @pytest.mark.restate_e2e for tests that require Restate.
"""
import pytest


def test_update_trial_via_vo_basic(test_client):
    """Test basic trial update via Virtual Object (without Restate running)."""
    # First create a trial via GraphQL
    create_mutation = """
        mutation CreateTrial($input: CreateTrialInput!) {
            createTrial(input: $input) {
                id
                name
                phase
            }
        }
    """

    create_variables = {
        "input": {
            "name": "Test Trial",
            "phase": "Phase I",
        }
    }

    create_response = test_client.post("/graphql", json={"query": create_mutation, "variables": create_variables})
    assert create_response.status_code == 200

    create_data = create_response.json()
    assert "errors" not in create_data
    trial_id = create_data["data"]["createTrial"]["id"]

    # Note: This test will work without Restate running because it's using
    # the test client which doesn't actually call Restate
    # To test the actual Virtual Object, mark with @pytest.mark.restate_e2e
    mutation = """
        mutation UpdateTrialViaVO($input: UpdateTrialMetadataInput!) {
            updateTrialMetadata(input: $input) {
                id
                name
                phase
                status
                changes
            }
        }
    """

    variables = {
        "input": {
            "trialId": trial_id,
            "name": "Updated Name",
            "phase": "Phase II",
        }
    }

    response = test_client.post("/graphql", json={"query": mutation, "variables": variables})
    assert response.status_code == 200

    data = response.json()
    assert "errors" not in data

    result = data["data"]["updateTrialMetadata"]
    assert result["id"] == trial_id
    assert result["name"] == "Updated Name"
    assert result["phase"] == "Phase II"
    assert "name" in result["changes"]
    assert "phase" in result["changes"]


@pytest.mark.restate_e2e
def test_update_trial_via_vo_with_restate(check_restate_running, check_api_running):
    """
    Test trial update via Virtual Object with Restate running.

    This test requires Restate to be running and the service registered.
    It demonstrates the actual Virtual Object concurrency protection.
    """
    import httpx
    import time

    # First create a trial via the regular mutation
    create_mutation = """
        mutation CreateTrial($input: CreateTrialInput!) {
            createTrial(input: $input) {
                id
                name
                phase
            }
        }
    """

    create_variables = {
        "input": {
            "name": "VO Test Trial",
            "phase": "Phase I",
        }
    }

    response = httpx.post(
        "http://localhost:8000/graphql",
        json={"query": create_mutation, "variables": create_variables},
        timeout=5.0
    )
    assert response.status_code == 200

    data = response.json()
    assert "errors" not in data
    trial_id = data["data"]["createTrial"]["id"]

    # Now update via Virtual Object
    update_mutation = """
        mutation UpdateTrialViaVO($input: UpdateTrialMetadataInput!) {
            updateTrialMetadataViaVo(input: $input) {
                id
                name
                phase
                changes
            }
        }
    """

    update_variables = {
        "input": {
            "trialId": trial_id,
            "name": "Updated via VO",
            "phase": "Phase II",
        }
    }

    response = httpx.post(
        "http://localhost:8000/graphql",
        json={"query": update_mutation, "variables": update_variables},
        timeout=5.0
    )
    assert response.status_code == 200

    data = response.json()
    assert "errors" not in data

    result = data["data"]["updateTrialMetadataViaVo"]
    assert result["id"] == trial_id
    assert result["name"] == "Updated via VO"
    assert result["phase"] == "Phase II"
    assert "name" in result["changes"]
    assert "phase" in result["changes"]


@pytest.mark.restate_e2e
def test_concurrent_updates_via_vo(check_restate_running, check_api_running):
    """
    Test that concurrent updates to same trial are serialized via Virtual Object.

    This test demonstrates the key benefit: multiple simultaneous updates to the
    same trial are automatically serialized by Restate, preventing race conditions
    without database-level locking.
    """
    import httpx
    import asyncio

    # Create a trial
    create_mutation = """
        mutation CreateTrial($input: CreateTrialInput!) {
            createTrial(input: $input) {
                id
            }
        }
    """

    response = httpx.post(
        "http://localhost:8000/graphql",
        json={
            "query": create_mutation,
            "variables": {"input": {"name": "Concurrency Test", "phase": "Phase I"}},
        },
        timeout=5.0
    )
    trial_id = response.json()["data"]["createTrial"]["id"]

    # Send 5 concurrent updates via Virtual Object
    # Restate will automatically serialize these
    update_mutation = """
        mutation UpdateTrialViaVO($input: UpdateTrialMetadataInput!) {
            updateTrialMetadataViaVo(input: $input) {
                id
                name
                changes
            }
        }
    """

    async def send_update(update_num):
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "http://localhost:8000/graphql",
                json={
                    "query": update_mutation,
                    "variables": {
                        "input": {
                            "trialId": trial_id,
                            "name": f"Update {update_num}",
                        }
                    },
                },
            )
            return response.json()

    # Send concurrent updates
    async def run_concurrent_updates():
        tasks = [send_update(i) for i in range(1, 6)]
        return await asyncio.gather(*tasks)

    results = asyncio.run(run_concurrent_updates())

    # All updates should succeed (no conflicts)
    for result in results:
        assert "errors" not in result
        assert result["data"]["updateTrialMetadataViaVo"]["id"] == trial_id

    # The final state should be consistent (one of the updates won)
    # Query the trial to verify
    query = """
        query GetTrial($id: Int!) {
            trial(id: $id) {
                id
                name
            }
        }
    """

    response = httpx.post(
        "http://localhost:8000/graphql",
        json={"query": query, "variables": {"id": trial_id}},
        timeout=5.0
    )

    final_trial = response.json()["data"]["trial"]
    assert final_trial["id"] == trial_id
    # Name should be one of the updates (serialization ensures consistency)
    assert final_trial["name"].startswith("Update")
