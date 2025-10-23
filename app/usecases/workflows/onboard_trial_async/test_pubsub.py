"""
Unit tests for workflow pub/sub mechanism.
"""
import pytest

from app.usecases.workflows.onboard_trial_async.pubsub import WorkflowPubSub
from app.usecases.workflows.onboard_trial_async.types import WorkflowProgressUpdate


@pytest.mark.asyncio
async def test_subscribe_and_publish():
    """Test basic subscribe and publish flow."""
    pubsub = WorkflowPubSub()
    workflow_id = "test-workflow-123"

    # Subscribe
    queue = await pubsub.subscribe(workflow_id)

    # Publish update
    update = WorkflowProgressUpdate(
        workflow_id=workflow_id,
        status="trial_created",
        message="Trial created successfully",
        trial_id=42,
    )
    await pubsub.publish(update)

    # Should receive the update
    received = await queue.get()
    assert received.workflow_id == workflow_id
    assert received.status == "trial_created"
    assert received.trial_id == 42

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
    update = WorkflowProgressUpdate(
        workflow_id=workflow_id,
        status="completed",
        message="Workflow completed",
    )
    await pubsub.publish(update)

    # Both should receive
    received1 = await queue1.get()
    received2 = await queue2.get()

    assert received1.status == "completed"
    assert received2.status == "completed"

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
    update = WorkflowProgressUpdate(
        workflow_id=workflow_id,
        status="failed",
        message="Should not receive this",
    )
    await pubsub.publish(update)

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
    update1 = WorkflowProgressUpdate(
        workflow_id=workflow_id_1,
        status="started",
        message="Workflow 1 started",
    )
    await pubsub.publish(update1)

    # Only queue1 should receive
    received1 = await queue1.get()
    assert received1.workflow_id == workflow_id_1

    # queue2 should be empty
    assert queue2.empty()

    # Cleanup
    pubsub.unsubscribe(workflow_id_1, queue1)
    pubsub.unsubscribe(workflow_id_2, queue2)
