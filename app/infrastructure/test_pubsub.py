"""
Unit tests for workflow pub/sub mechanism.
"""
import pytest

from app.infrastructure.pubsub import WorkflowPubSub
from app.usecases.workflows.onboard_trial_async.types import (
    OnboardTrialProgressUpdate,
    OnboardTrialStatus,
    TrialData,
)


@pytest.mark.asyncio
async def test_subscribe_and_publish():
    """Test basic subscribe and publish flow with strongly-typed updates."""
    pubsub = WorkflowPubSub()
    workflow_id = "test-workflow-123"

    # Subscribe
    queue = await pubsub.subscribe(workflow_id)

    # Publish update with trial data
    trial_data = TrialData(id=42, name="Test Trial", phase="Phase I")
    update = OnboardTrialProgressUpdate(
        workflow_id=workflow_id,
        status=OnboardTrialStatus.TRIAL_CREATED,
        message="Trial created successfully",
        trial=trial_data,
    )
    await pubsub.publish(workflow_id, update)

    # Should receive the update
    received = await queue.get()
    assert received.workflow_id == workflow_id
    assert received.status == OnboardTrialStatus.TRIAL_CREATED
    assert received.trial.id == 42
    assert received.trial.name == "Test Trial"

    # Cleanup
    pubsub.unsubscribe(workflow_id, queue)


@pytest.mark.asyncio
async def test_multiple_subscribers():
    """Test that multiple subscribers receive the same update."""
    pubsub = WorkflowPubSub()
    workflow_id = "test-workflow-456"

    # Subscribe with two clients
    queue1 = await pubsub.subscribe(workflow_id)
    queue2 = await pubsub.subscribe(workflow_id)

    # Publish update
    update = OnboardTrialProgressUpdate(
        workflow_id=workflow_id,
        status=OnboardTrialStatus.COMPLETED,
        message="Workflow completed",
    )
    await pubsub.publish(workflow_id, update)

    # Both should receive
    received1 = await queue1.get()
    received2 = await queue2.get()

    assert received1.status == OnboardTrialStatus.COMPLETED
    assert received2.status == OnboardTrialStatus.COMPLETED

    # Cleanup
    pubsub.unsubscribe(workflow_id, queue1)
    pubsub.unsubscribe(workflow_id, queue2)


@pytest.mark.asyncio
async def test_unsubscribe():
    """Test that unsubscribe stops receiving updates."""
    pubsub = WorkflowPubSub()
    workflow_id = "test-workflow-789"

    # Subscribe
    queue = await pubsub.subscribe(workflow_id)

    # Unsubscribe immediately
    pubsub.unsubscribe(workflow_id, queue)

    # Publish update
    update = OnboardTrialProgressUpdate(
        workflow_id=workflow_id,
        status=OnboardTrialStatus.FAILED,
        message="Should not receive this",
    )
    await pubsub.publish(workflow_id, update)

    # Queue should be empty (no update received)
    assert queue.empty()


@pytest.mark.asyncio
async def test_isolated_workflows():
    """Test that workflows are isolated from each other."""
    pubsub = WorkflowPubSub()
    workflow_id_1 = "workflow-1"
    workflow_id_2 = "workflow-2"

    # Subscribe to both
    queue1 = await pubsub.subscribe(workflow_id_1)
    queue2 = await pubsub.subscribe(workflow_id_2)

    # Publish to workflow 1 only
    update1 = OnboardTrialProgressUpdate(
        workflow_id=workflow_id_1,
        status=OnboardTrialStatus.CREATING_TRIAL,
        message="Workflow 1 started",
    )
    await pubsub.publish(workflow_id_1, update1)

    # Only queue1 should receive
    received1 = await queue1.get()
    assert received1.workflow_id == workflow_id_1

    # queue2 should be empty
    assert queue2.empty()

    # Cleanup
    pubsub.unsubscribe(workflow_id_1, queue1)
    pubsub.unsubscribe(workflow_id_2, queue2)
