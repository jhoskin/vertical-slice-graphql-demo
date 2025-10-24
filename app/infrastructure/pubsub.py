"""
In-memory pub/sub system for workflow progress updates.

This implementation provides a simple, in-memory message broker for
workflow-specific real-time updates via GraphQL subscriptions.

Example usage:
    from app.infrastructure.pubsub import workflow_pubsub

    # Publish an update
    await workflow_pubsub.publish(workflow_id, update_data)

    # Subscribe to updates
    queue = await workflow_pubsub.subscribe(workflow_id)
    update = await queue.get()
"""
import asyncio
from collections import defaultdict
from typing import Any, Dict

from app.usecases.workflows.onboard_trial_async.types import OnboardTrialProgressUpdate


class WorkflowPubSub:
    """
    In-memory pub/sub for workflow progress updates.

    This is a simple implementation suitable for single-server deployments.
    For multi-server setups, use Redis pub/sub or similar distributed solution.
    """

    def __init__(self):
        """Initialize the pub/sub system."""
        # workflow_id -> list of subscriber queues
        self._subscribers: Dict[str, list[asyncio.Queue]] = defaultdict(list)

    async def subscribe(self, workflow_id: str) -> asyncio.Queue:
        """
        Subscribe to updates for a specific workflow.

        Args:
            workflow_id: The workflow to subscribe to

        Returns:
            A queue that will receive OnboardTrialProgressUpdate messages
        """
        queue: asyncio.Queue[OnboardTrialProgressUpdate] = asyncio.Queue()
        self._subscribers[workflow_id].append(queue)
        return queue

    def unsubscribe(self, workflow_id: str, queue: asyncio.Queue) -> None:
        """
        Unsubscribe from workflow updates.

        Args:
            workflow_id: The workflow to unsubscribe from
            queue: The queue to remove
        """
        if workflow_id in self._subscribers:
            try:
                self._subscribers[workflow_id].remove(queue)
                # Clean up empty subscriber lists
                if not self._subscribers[workflow_id]:
                    del self._subscribers[workflow_id]
            except ValueError:
                # Queue already removed
                pass

    async def publish(self, workflow_id: str, update: OnboardTrialProgressUpdate) -> None:
        """
        Publish an update to all subscribers of a workflow.

        Args:
            workflow_id: The workflow that has an update
            update: The progress update to publish
        """
        if workflow_id in self._subscribers:
            # Send to all subscribers
            for queue in self._subscribers[workflow_id]:
                await queue.put(update)


# Global singleton instance
workflow_pubsub = WorkflowPubSub()
