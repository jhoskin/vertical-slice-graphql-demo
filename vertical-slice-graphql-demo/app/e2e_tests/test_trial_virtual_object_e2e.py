"""
End-to-end tests for Trial Virtual Object mutation.

These tests verify that the updateTrialMetadataViaVO mutation works correctly
and demonstrate the concurrency protection benefits.

Note: Full concurrency testing requires Restate to be running.
Mark with @pytest.mark.restate_e2e for tests that require Restate.
"""
import httpx
import pytest


@pytest.fixture(scope="module")
def check_restate_running():
    """Check that Restate is running before running tests."""
    try:
        response = httpx.get("http://localhost:9070/health", timeout=2.0)
        if response.status_code != 200:
            pytest.skip("Restate is not running. Start with: docker-compose up")
    except Exception:
        pytest.skip("Restate is not running. Start with: docker-compose up")


@pytest.fixture(scope="module")
def check_api_running():
    """Check that GraphQL API is running."""
    try:
        response = httpx.get("http://localhost:8000/", timeout=2.0)
        if response.status_code != 200:
            pytest.skip("API is not running. Start with: docker-compose up")
    except Exception:
        pytest.skip("API is not running. Start with: docker-compose up")


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
        query GetTrial($id: String!) {
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


def test_stale_data_protection_basic(test_client):
    """
    Test that stale data is rejected when using expected_updated_at.

    This test demonstrates optimistic locking: if a client tries to update
    based on an old timestamp of the data, the update is rejected.
    """
    # Create a trial
    create_mutation = """
        mutation CreateTrial($input: CreateTrialInput!) {
            createTrial(input: $input) {
                id
                name
                phase
                updatedAt
            }
        }
    """

    create_variables = {
        "input": {
            "name": "Stale Data Test",
            "phase": "Phase I",
        }
    }

    create_response = test_client.post("/graphql", json={"query": create_mutation, "variables": create_variables})
    assert create_response.status_code == 200

    create_data = create_response.json()
    assert "errors" not in create_data
    trial_id = create_data["data"]["createTrial"]["id"]
    initial_updated_at = create_data["data"]["createTrial"]["updatedAt"]
    assert initial_updated_at  # Has initial timestamp

    # First update (should succeed with correct timestamp)
    update_mutation = """
        mutation UpdateTrial($input: UpdateTrialMetadataInput!) {
            updateTrialMetadata(input: $input) {
                id
                name
                updatedAt
                changes
            }
        }
    """

    update1_variables = {
        "input": {
            "trialId": trial_id,
            "name": "First Update",
            "expectedUpdatedAt": initial_updated_at,
        }
    }

    update1_response = test_client.post("/graphql", json={"query": update_mutation, "variables": update1_variables})
    assert update1_response.status_code == 200

    update1_data = update1_response.json()
    assert "errors" not in update1_data
    assert update1_data["data"]["updateTrialMetadata"]["name"] == "First Update"
    new_updated_at = update1_data["data"]["updateTrialMetadata"]["updatedAt"]
    assert new_updated_at != initial_updated_at  # Timestamp changed

    # Second update with STALE timestamp (should fail)
    update2_variables = {
        "input": {
            "trialId": trial_id,
            "name": "Stale Update",
            "expectedUpdatedAt": initial_updated_at,  # Using old timestamp!
        }
    }

    update2_response = test_client.post("/graphql", json={"query": update_mutation, "variables": update2_variables})
    assert update2_response.status_code == 200

    update2_data = update2_response.json()
    # Should have an error about timestamp mismatch
    assert "errors" in update2_data
    error_message = update2_data["errors"][0]["message"]
    assert "timestamp mismatch" in error_message.lower() or "stale" in error_message.lower()

    # Third update with CORRECT timestamp (should succeed)
    update3_variables = {
        "input": {
            "trialId": trial_id,
            "name": "Fresh Update",
            "expectedUpdatedAt": new_updated_at,  # Using current timestamp
        }
    }

    update3_response = test_client.post("/graphql", json={"query": update_mutation, "variables": update3_variables})
    assert update3_response.status_code == 200

    update3_data = update3_response.json()
    assert "errors" not in update3_data
    assert update3_data["data"]["updateTrialMetadata"]["name"] == "Fresh Update"


@pytest.mark.restate_e2e
def test_stale_data_protection_via_vo(check_restate_running, check_api_running):
    """
    Test stale data protection via Virtual Object with Restate.

    This demonstrates that version checking works correctly even when
    updates are serialized through Restate's Virtual Object.
    The VO provides serialization for concurrent writes from different clients,
    while version checking protects against stale data from the same client.
    """
    import httpx

    # Create a trial
    create_mutation = """
        mutation CreateTrial($input: CreateTrialInput!) {
            createTrial(input: $input) {
                id
                updatedAt
            }
        }
    """

    response = httpx.post(
        "http://localhost:8000/graphql",
        json={
            "query": create_mutation,
            "variables": {"input": {"name": "VO Stale Test", "phase": "Phase I"}},
        },
        timeout=5.0
    )
    assert response.status_code == 200

    data = response.json()
    assert "errors" not in data
    trial_id = data["data"]["createTrial"]["id"]
    initial_updated_at = data["data"]["createTrial"]["updatedAt"]

    # First update via VO (should succeed)
    update_mutation = """
        mutation UpdateTrialViaVO($input: UpdateTrialMetadataInput!) {
            updateTrialMetadataViaVo(input: $input) {
                id
                name
                updatedAt
            }
        }
    """

    response1 = httpx.post(
        "http://localhost:8000/graphql",
        json={
            "query": update_mutation,
            "variables": {
                "input": {
                    "trialId": trial_id,
                    "name": "VO Update 1",
                    "expectedUpdatedAt": initial_updated_at,
                }
            },
        },
        timeout=5.0
    )
    assert response1.status_code == 200

    data1 = response1.json()
    assert "errors" not in data1
    new_updated_at = data1["data"]["updateTrialMetadataViaVo"]["updatedAt"]
    assert new_updated_at != initial_updated_at  # Timestamp should have changed

    # Second update via VO with stale timestamp (should fail)
    response2 = httpx.post(
        "http://localhost:8000/graphql",
        json={
            "query": update_mutation,
            "variables": {
                "input": {
                    "trialId": trial_id,
                    "name": "VO Stale Update",
                    "expectedUpdatedAt": initial_updated_at,  # Stale!
                }
            },
        },
        timeout=5.0
    )
    assert response2.status_code == 200

    data2 = response2.json()
    # Should have error about timestamp mismatch
    assert "errors" in data2
    error_message = data2["errors"][0]["message"]
    assert "timestamp mismatch" in error_message.lower() or "stale" in error_message.lower()

    # Third update with correct timestamp (should succeed)
    response3 = httpx.post(
        "http://localhost:8000/graphql",
        json={
            "query": update_mutation,
            "variables": {
                "input": {
                    "trialId": trial_id,
                    "name": "VO Fresh Update",
                    "expectedUpdatedAt": new_updated_at,  # Fresh!
                }
            },
        },
        timeout=5.0
    )
    assert response3.status_code == 200

    data3 = response3.json()
    assert "errors" not in data3
    assert data3["data"]["updateTrialMetadataViaVo"]["updatedAt"] != initial_updated_at  # Changed again
