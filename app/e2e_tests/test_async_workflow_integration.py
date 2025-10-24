"""
E2E tests for asynchronous Restate workflow.

Note: These tests focus on the GraphQL API, webhook, and subscription mechanisms.
Full integration with Restate runtime requires Restate to be running and is tested manually.
"""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.infrastructure.pubsub import workflow_pubsub
from app.usecases.workflows.onboard_trial_async.types import (
    OnboardTrialProgressUpdate,
    OnboardTrialStatus,
    TrialData,
)
from app.usecases.workflows.onboard_trial_async.webhook import router as webhook_router


@pytest.fixture
def webhook_client():
    """Create a test client with webhook endpoint."""
    app = FastAPI()
    app.include_router(webhook_router)
    with TestClient(app) as client:
        yield client


@patch("httpx.AsyncClient.post")
def test_start_async_workflow_returns_workflow_id(
    mock_post: AsyncMock, test_client, graphql_client
):
    """Test that starting async workflow returns workflow ID immediately."""
    # Mock the Restate HTTP call
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

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
            "name": "Async Test Trial",
            "phase": "Phase I",
            "initialProtocolVersion": "v1.0",
            "sites": [{"name": "Site A", "country": "USA"}],
        }
    }

    result = graphql_client(mutation, variables)

    assert "errors" not in result

    data = result["data"]["startOnboardTrialAsync"]

    # Should return immediately with workflow ID
    assert "workflowId" in data
    assert data["workflowId"] is not None
    assert len(data["workflowId"]) > 0
    assert "message" in data
    assert "Workflow started" in data["message"]

    # Verify Restate was called
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert "OnboardTrialWorkflow" in call_args[0][0]
    assert "/run/send" in call_args[0][0]


def test_webhook_receives_progress(webhook_client: TestClient):
    """Test that webhook endpoint receives and processes strongly-typed progress updates."""
    workflow_id = "test-webhook-123"

    payload = {
        "workflow_id": workflow_id,
        "status": "trial_created",
        "message": "Trial created successfully",
        "trial": {
            "id": 42,
            "name": "Test Trial",
            "phase": "Phase I"
        },
    }

    response = webhook_client.post("/api/workflows/progress", json=payload)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_webhook_publishes_to_subscriptions(webhook_client: TestClient):
    """Test that webhook publishes strongly-typed updates to pub/sub for subscriptions."""
    workflow_id = "test-pubsub-webhook-456"

    # Subscribe before sending webhook
    queue = await workflow_pubsub.subscribe(workflow_id)

    try:
        # Send webhook request
        payload = {
            "workflow_id": workflow_id,
            "status": "protocol_added",
            "message": "Protocol added",
            "trial": {
                "id": 99,
                "name": "Test Trial",
                "phase": "Phase I"
            },
        }

        response = webhook_client.post("/api/workflows/progress", json=payload)
        assert response.status_code == 200

        # Should receive the update via pub/sub
        # Wait a bit for async processing
        await asyncio.sleep(0.1)

        # Check queue has the update
        assert not queue.empty()
        update = await queue.get()
        assert update.workflow_id == workflow_id
        assert update.status == OnboardTrialStatus.PROTOCOL_ADDED
        assert update.trial.id == 99

    finally:
        workflow_pubsub.unsubscribe(workflow_id, queue)


@pytest.mark.asyncio
async def test_multiple_progress_updates(webhook_client: TestClient):
    """Test receiving multiple progress updates for a workflow."""
    workflow_id = "test-multiple-789"

    # Subscribe
    queue = await workflow_pubsub.subscribe(workflow_id)

    trial_data = {"id": 123, "name": "Test Trial", "phase": "Phase I"}

    try:
        # Send multiple webhook requests simulating workflow progress
        updates = [
            {"workflow_id": workflow_id, "status": "creating_trial", "message": "Creating trial..."},
            {"workflow_id": workflow_id, "status": "trial_created", "message": "Trial created", "trial": trial_data},
            {"workflow_id": workflow_id, "status": "protocol_adding", "message": "Adding protocol...", "trial": trial_data},
            {"workflow_id": workflow_id, "status": "completed", "message": "Workflow completed", "trial": trial_data},
        ]

        for update_payload in updates:
            response = webhook_client.post("/api/workflows/progress", json=update_payload)
            assert response.status_code == 200
            await asyncio.sleep(0.05)

        # Should have received all updates
        received_updates = []
        while not queue.empty():
            update = await queue.get()
            received_updates.append(update.status)

        assert len(received_updates) == 4
        assert OnboardTrialStatus.CREATING_TRIAL in received_updates
        assert OnboardTrialStatus.TRIAL_CREATED in received_updates
        assert OnboardTrialStatus.PROTOCOL_ADDING in received_updates
        assert OnboardTrialStatus.COMPLETED in received_updates

    finally:
        workflow_pubsub.unsubscribe(workflow_id, queue)


@pytest.mark.asyncio
async def test_subscription_isolation(webhook_client: TestClient):
    """Test that subscriptions for different workflows are isolated."""
    workflow_id_1 = "workflow-a"
    workflow_id_2 = "workflow-b"

    # Subscribe to both
    queue1 = await workflow_pubsub.subscribe(workflow_id_1)
    queue2 = await workflow_pubsub.subscribe(workflow_id_2)

    try:
        # Send update for workflow 1
        response = webhook_client.post(
            "/api/workflows/progress",
            json={
                "workflow_id": workflow_id_1,
                "status": "creating_trial",
                "message": "Workflow 1 started",
            },
        )
        assert response.status_code == 200
        await asyncio.sleep(0.1)

        # Only queue1 should have the update
        assert not queue1.empty()
        assert queue2.empty()

        update = await queue1.get()
        assert update.workflow_id == workflow_id_1

    finally:
        workflow_pubsub.unsubscribe(workflow_id_1, queue1)
        workflow_pubsub.unsubscribe(workflow_id_2, queue2)


@pytest.mark.asyncio
async def test_workflow_progress_update_structure():
    """Test the structure of strongly-typed workflow progress updates."""
    trial_data = TrialData(id=42, name="Test Trial", phase="Phase I")
    update = OnboardTrialProgressUpdate(
        workflow_id="test-123",
        status=OnboardTrialStatus.TRIAL_CREATED,
        message="Trial created successfully",
        trial=trial_data,
    )

    assert update.workflow_id == "test-123"
    assert update.status == OnboardTrialStatus.TRIAL_CREATED
    assert update.message == "Trial created successfully"
    assert update.trial.id == 42
    assert update.trial.name == "Test Trial"


@pytest.mark.asyncio
async def test_workflow_progress_without_trial_id():
    """Test workflow progress update without trial data (early stages)."""
    update = OnboardTrialProgressUpdate(
        workflow_id="test-456",
        status=OnboardTrialStatus.CREATING_TRIAL,
        message="Creating trial...",
    )

    assert update.workflow_id == "test-456"
    assert update.status == OnboardTrialStatus.CREATING_TRIAL
    assert update.message == "Creating trial..."
    assert update.trial is None
