"""
Simple in-memory pub/sub for workflow progress updates.

This allows the Restate workflow to publish progress updates
that GraphQL subscriptions can consume.
"""
import asyncio
from collections import defaultdict
from typing import Dict, Set

from app.usecases.workflows.onboard_trial_async.types import WorkflowProgressUpdate


class WorkflowPubSub:
    """
    In-memory pub/sub for workflow progress updates.

    Note: This is a simple implementation suitable for single-instance deployments.
    For production with multiple instances, use Redis pub/sub or similar.
    """

    def __init__(self):
        self._queues: Dict[str, Set[asyncio.Queue]] = defaultdict(set)

    async def subscribe(self, workflow_id: str) -> asyncio.Queue:
        """Subscribe to updates for a specific workflow."""
        queue = asyncio.Queue()
        self._queues[workflow_id].add(queue)
        return queue

    def unsubscribe(self, workflow_id: str, queue: asyncio.Queue):
        """Unsubscribe from a workflow's updates."""
        if workflow_id in self._queues:
            self._queues[workflow_id].discard(queue)
            if not self._queues[workflow_id]:
                del self._queues[workflow_id]

    async def publish(self, update: WorkflowProgressUpdate):
        """Publish an update to all subscribers of a workflow."""
        workflow_id = update.workflow_id
        if workflow_id in self._queues:
            # Send to all subscribers
            for queue in self._queues[workflow_id]:
                await queue.put(update)


# Global instance
workflow_pubsub = WorkflowPubSub()
