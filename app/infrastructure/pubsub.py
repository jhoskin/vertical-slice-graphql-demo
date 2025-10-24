"""
Generic in-memory pub/sub for workflow progress updates.

This infrastructure component provides a reusable pub/sub mechanism for any
async workflow that needs to publish progress updates to subscribers.

Usage:
    from app.infrastructure.pubsub import workflow_pubsub

    # In workflow: publish updates
    await workflow_pubsub.publish(workflow_id, update_data)

    # In GraphQL subscription: subscribe to updates
    queue = await workflow_pubsub.subscribe(workflow_id)
    async for update in queue:
        yield update

Note: This is a simple in-memory implementation suitable for single-instance
deployments. For production with multiple instances, use Redis pub/sub or similar.
"""
import asyncio
from collections import defaultdict
from typing import Any, Dict, Set


class WorkflowPubSub:
    """
    Generic in-memory pub/sub for workflow progress updates.

    This implementation is workflow-agnostic - it accepts any data type as
    the update payload. Workflows are responsible for using strongly-typed
    update objects that subscribers understand.
    """

    def __init__(self):
        self._queues: Dict[str, Set[asyncio.Queue]] = defaultdict(set)

    async def subscribe(self, workflow_id: str) -> asyncio.Queue:
        """
        Subscribe to updates for a specific workflow.

        Args:
            workflow_id: Unique identifier for the workflow instance

        Returns:
            An asyncio.Queue that will receive all updates for this workflow
        """
        queue = asyncio.Queue()
        self._queues[workflow_id].add(queue)
        return queue

    def unsubscribe(self, workflow_id: str, queue: asyncio.Queue):
        """
        Unsubscribe from a workflow's updates.

        Args:
            workflow_id: Workflow identifier
            queue: The queue to unsubscribe
        """
        if workflow_id in self._queues:
            self._queues[workflow_id].discard(queue)
            if not self._queues[workflow_id]:
                del self._queues[workflow_id]

    async def publish(self, workflow_id: str, update: Any):
        """
        Publish an update to all subscribers of a workflow.

        Args:
            workflow_id: Workflow identifier
            update: The update data (typically a strongly-typed object)
        """
        if workflow_id in self._queues:
            # Send to all subscribers
            for queue in self._queues[workflow_id]:
                await queue.put(update)


# Global instance - single pub/sub for all workflows
workflow_pubsub = WorkflowPubSub()
