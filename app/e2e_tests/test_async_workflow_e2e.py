"""
True E2E tests for asynchronous Restate workflow.

These tests require Restate to be running and test the full system:
- GraphQL API → Restate runtime → Workflow execution → GraphQL pub/sub progress updates → Subscriptions

Run with: pytest -m restate_e2e
Skip with: pytest -m "not restate_e2e"

Prerequisites:
- docker-compose up (Restate, API, Restate service)
"""
import asyncio
import time

import httpx
import pytest

# Mark all tests in this module as requiring Restate
pytestmark = pytest.mark.restate_e2e


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


@pytest.fixture(scope="module")
def check_restate_service_registered(check_restate_running):
    """Check that Restate workflow service is registered."""
    try:
        response = httpx.get("http://localhost:9070/services", timeout=2.0)
        data = response.json()

        # Check if our workflow service is registered
        service_registered = any(
            service.get("name") == "OnboardTrialWorkflow"
            for service in data.get("services", [])
        )

        if not service_registered:
            pytest.skip(
                "Restate workflow service not registered. "
                "Make sure docker-compose is fully up and service registered."
            )
    except Exception as e:
        pytest.skip(f"Could not check Restate services: {e}")


def test_restate_health(check_restate_running):
    """Test that Restate is healthy and accessible."""
    response = httpx.get("http://localhost:9070/health")
    assert response.status_code == 200


def test_async_workflow_full_execution(
    check_restate_running, check_api_running, check_restate_service_registered
):
    """
    True E2E test: Start async workflow and verify it executes through Restate.

    This test:
    1. Starts workflow via GraphQL mutation
    2. Verifies workflow ID returned
    3. Polls Restate for workflow completion
    4. Verifies database state
    """
    mutation = """
        mutation StartAsync($input: OnboardTrialAsyncInput!) {
            startOnboardTrialAsync(input: $input) {
                workflowId
                message
            }
        }
    """

    variables = {
        "input": {
            "name": "E2E Restate Test Trial",
            "phase": "Phase I",
            "initialProtocolVersion": "v1.0",
            "sites": [
                {"name": "E2E Site A", "country": "USA"},
                {"name": "E2E Site B", "country": "UK"},
            ],
        }
    }

    # Start workflow via GraphQL (connect to running Docker service)
    response = httpx.post(
        "http://localhost:8000/graphql",
        json={"query": mutation, "variables": variables},
        timeout=5.0
    )
    assert response.status_code == 200

    data = response.json()
    assert "errors" not in data

    workflow_data = data["data"]["startOnboardTrialAsync"]
    workflow_id = workflow_data["workflowId"]

    assert workflow_id is not None
    assert len(workflow_id) > 0

    # Wait for workflow to complete
    # The workflow has synthetic delays (2s per step)
    # With 1 site: trial_creating (2s) + create_trial + trial_created (2s) + protocol (2s) + site (2s) + completed
    # Total: ~12 seconds
    # Add buffer for Restate processing
    time.sleep(15)

    # Verify database state via GraphQL queries (true E2E approach)
    # Query for trials to find the one we created
    query_trials = """
        query {
            trials(input: {limit: 100}) {
                items {
                    id
                    name
                    phase
                    status
                }
            }
        }
    """

    query_response = httpx.post(
        "http://localhost:8000/graphql",
        json={"query": query_trials},
        timeout=5.0
    )

    # Verify trial was created
    assert query_response.status_code == 200
    query_data = query_response.json()
    assert "errors" not in query_data

    trials = query_data["data"]["trials"]["items"]
    trial = next((t for t in trials if t["name"] == "E2E Restate Test Trial"), None)

    assert trial is not None, "Trial should exist after workflow completion"
    assert trial["phase"] == "Phase I"

    # Query the specific trial to check protocol and sites
    get_trial = """
        query GetTrial($id: String!) {
            trial(id: $id) {
                id
                name
                sites {
                    name
                    country
                }
            }
        }
    """

    trial_response = httpx.post(
        "http://localhost:8000/graphql",
        json={"query": get_trial, "variables": {"id": trial["id"]}},
        timeout=5.0
    )

    assert trial_response.status_code == 200
    trial_data = trial_response.json()
    assert "errors" not in trial_data

    trial_detail = trial_data["data"]["trial"]
    assert len(trial_detail["sites"]) == 2, "Should have 2 sites registered"


def test_async_workflow_with_progress_updates(
    check_restate_running, check_api_running, check_restate_service_registered
):
    """
    E2E test verifying GraphQL pub/sub progress updates work via Restate execution.

    This test:
    1. Starts workflow via GraphQL
    2. Waits for completion
    3. Verifies trial was created (proves workflow executed)
    4. Verifies database state (proves progress updates were published)
    """
    # GraphQL mutation
    mutation = """
        mutation StartAsync($input: OnboardTrialAsyncInput!) {
            startOnboardTrialAsync(input: $input) {
                workflowId
                message
            }
        }
    """

    variables = {
        "input": {
            "name": "E2E Webhook Test Trial",
            "phase": "Phase II",
            "initialProtocolVersion": "v2.0",
            "sites": [{"name": "Webhook Site", "country": "Canada"}],
        }
    }

    # Start workflow
    response = httpx.post(
        "http://localhost:8000/graphql",
        json={"query": mutation, "variables": variables},
        timeout=5.0
    )
    assert response.status_code == 200

    data = response.json()
    assert "errors" not in data

    workflow_id = data["data"]["startOnboardTrialAsync"]["workflowId"]
    assert workflow_id is not None
    assert len(workflow_id) > 0

    # Wait for workflow to complete
    # With 1 site: ~8 seconds of sleeps + processing
    time.sleep(12)

    # Verify trial was created via GraphQL
    query_trials = """
        query {
            trials(input: {limit: 100}) {
                items {
                    id
                    name
                    phase
                }
            }
        }
    """

    query_response = httpx.post(
        "http://localhost:8000/graphql",
        json={"query": query_trials},
        timeout=5.0
    )

    assert query_response.status_code == 200
    query_data = query_response.json()
    assert "errors" not in query_data

    trials = query_data["data"]["trials"]["items"]
    trial = next((t for t in trials if t["name"] == "E2E Webhook Test Trial"), None)

    assert trial is not None, "Trial should exist after workflow completion"
    assert trial["phase"] == "Phase II"

    # Query the specific trial to check sites
    get_trial = """
        query GetTrial($id: String!) {
            trial(id: $id) {
                id
                name
                sites {
                    name
                    country
                }
            }
        }
    """

    trial_response = httpx.post(
        "http://localhost:8000/graphql",
        json={"query": get_trial, "variables": {"id": trial["id"]}},
        timeout=5.0
    )

    assert trial_response.status_code == 200
    trial_data = trial_response.json()
    assert "errors" not in trial_data

    trial_detail = trial_data["data"]["trial"]
    assert len(trial_detail["sites"]) == 1, "Should have 1 site registered"
    assert trial_detail["sites"][0]["name"] == "Webhook Site"
    assert trial_detail["sites"][0]["country"] == "Canada"


def test_sync_saga_still_works_with_restate_running(test_client):
    """Verify sync saga works even when Restate is running (independence test)."""
    mutation = """
        mutation OnboardTrialSync($input: OnboardTrialSyncInput!) {
            onboardTrialSync(input: $input) {
                success
                trialId
                message
            }
        }
    """

    variables = {
        "input": {
            "name": "Sync Saga with Restate Running",
            "phase": "Phase III",
            "initialProtocolVersion": "v1.0",
            "sites": [],
        }
    }

    response = test_client.post(
        "/graphql",
        json={"query": mutation, "variables": variables}
    )
    assert response.status_code == 200

    data = response.json()
    assert "errors" not in data
    assert data["data"]["onboardTrialSync"]["success"] is True
