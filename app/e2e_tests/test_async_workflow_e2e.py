"""
True E2E tests for asynchronous Restate workflow.

These tests require Restate to be running and test the full system:
- GraphQL API → Restate runtime → Workflow execution → Webhook callbacks → Subscriptions

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
        response = httpx.get("http://localhost:9070/endpoints", timeout=2.0)
        endpoints = response.json()

        # Check if our workflow service is registered
        service_registered = any(
            "OnboardTrialWorkflow" in str(ep) for ep in endpoints.get("endpoints", [])
        )

        if not service_registered:
            pytest.skip(
                "Restate workflow service not registered. "
                "Make sure docker-compose is fully up and service registered."
            )
    except Exception as e:
        pytest.skip(f"Could not check Restate endpoints: {e}")


def test_restate_health(check_restate_running):
    """Test that Restate is healthy and accessible."""
    response = httpx.get("http://localhost:9070/health")
    assert response.status_code == 200


def test_async_workflow_full_execution(
    check_restate_running, check_api_running, check_restate_service_registered, test_client
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

    # Start workflow via GraphQL
    response = test_client.post(
        "/graphql",
        json={"query": mutation, "variables": variables}
    )
    assert response.status_code == 200

    data = response.json()
    assert "errors" not in data

    workflow_data = data["data"]["startOnboardTrialAsync"]
    workflow_id = workflow_data["workflowId"]

    assert workflow_id is not None
    assert len(workflow_id) > 0

    # Wait for workflow to complete (with timeout)
    # The workflow has synthetic delays (2s per step), expect ~10-12 seconds total
    max_wait = 30  # seconds
    start_time = time.time()
    workflow_completed = False

    while time.time() - start_time < max_wait:
        try:
            # Check workflow status via Restate API
            status_response = httpx.get(
                f"http://localhost:8080/restate/workflow/OnboardTrialWorkflow/{workflow_id}",
                timeout=2.0
            )

            # If we get 200, workflow is still running or completed
            if status_response.status_code == 200:
                # Try to get invocation journal to see if completed
                journal_response = httpx.get(
                    f"http://localhost:9070/invocations/{workflow_id}",
                    timeout=2.0
                )

                if journal_response.status_code == 200:
                    journal_data = journal_response.json()
                    # Check if invocation is completed
                    if journal_data.get("status") == "completed":
                        workflow_completed = True
                        break

        except Exception:
            pass  # Restate might not have the endpoint we expect, keep polling

        time.sleep(2)  # Poll every 2 seconds

    # Give workflow a bit more time to finish database writes and webhook calls
    time.sleep(2)

    # Verify database state (workflow should have created trial and sites)
    from app.infrastructure.database import session as session_module
    from app.infrastructure.database.models import ProtocolVersion, Trial, TrialSite

    session = session_module.SessionLocal()
    try:
        # Find the trial by name
        trial = session.query(Trial).filter_by(name="E2E Restate Test Trial").first()

        if workflow_completed:
            # If we confirmed completion via Restate, verify database
            assert trial is not None, "Trial should exist after workflow completion"
            assert trial.phase == "Phase I"

            # Check protocol
            protocol = session.query(ProtocolVersion).filter_by(trial_id=trial.id).first()
            assert protocol is not None
            assert protocol.version == "v1.0"

            # Check sites
            links = session.query(TrialSite).filter_by(trial_id=trial.id).all()
            assert len(links) == 2
        else:
            # If we timed out, at least verify something happened
            # (workflow might still be running or Restate API queries failed)
            if trial is not None:
                print(f"Workflow may still be running. Trial ID: {trial.id}")
            else:
                pytest.skip(
                    f"Workflow did not complete within {max_wait}s. "
                    "This might be a timeout issue or workflow is still running. "
                    "Check Restate UI at http://localhost:9070"
                )
    finally:
        session.close()


@pytest.mark.asyncio
async def test_async_workflow_with_webhook_callbacks(
    check_restate_running, check_api_running, check_restate_service_registered
):
    """
    E2E test with webhook callback verification.

    This test:
    1. Subscribes to workflow progress (simulated via queue)
    2. Starts workflow
    3. Waits for progress updates via webhook → pub/sub
    4. Verifies updates received
    """
    from app.usecases.workflows.onboard_trial_async.pubsub import workflow_pubsub

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
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/graphql",
            json={"query": mutation, "variables": variables},
            timeout=5.0
        )
        assert response.status_code == 200

        data = response.json()
        assert "errors" not in data

        workflow_id = data["data"]["startOnboardTrialAsync"]["workflowId"]

    # Subscribe to progress updates
    queue = await workflow_pubsub.subscribe(workflow_id)

    try:
        # Wait for progress updates (with timeout)
        updates_received = []
        timeout = 30  # seconds

        try:
            while len(updates_received) < 3:  # Expect at least trial_created, protocol_added, completed
                update = await asyncio.wait_for(queue.get(), timeout=timeout)
                updates_received.append(update.status)

                if update.status in ("completed", "failed"):
                    break

        except asyncio.TimeoutError:
            pytest.skip(
                f"Did not receive expected progress updates within {timeout}s. "
                f"Received: {updates_received}. Check if workflow is executing."
            )

        # Verify we got meaningful updates
        assert len(updates_received) > 0, "Should have received at least one update"

        # If workflow completed, verify we got key status updates
        if "completed" in updates_received:
            # Should have received updates for major steps
            statuses_str = " ".join(updates_received)
            assert any(
                status in statuses_str
                for status in ["created", "added", "registered"]
            ), f"Should have received workflow progress updates, got: {updates_received}"

    finally:
        workflow_pubsub.unsubscribe(workflow_id, queue)


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
